"""Import documents, queue their audio and run each audio job stage.

The job runner (`services/runner.py`) calls the stages; it runs a single
narration worker, so synthesis happens one audio at a time.
"""

from collections.abc import Callable
from pathlib import Path
from typing import overload

import structlog

from phemius.config import load_config
from phemius.errors import NotFoundError, PhemiusError, VoiceError
from phemius.services import agent, ffmpeg, ingest, narration_parts, queue, voices
from phemius.services.usage import job_usage
from phemius.store import audio as audio_store
from phemius.store import documents as document_store
from phemius.store import jobs as job_store
from phemius.store.documents import (
    Document,
    ExcludedItem,
    NewDocument,
    StoredVersion,
)
from phemius.store.jobs import AudioFile, AudioFormat, ClaimedJob, QueuedAudio
from phemius.store.permissions import create_private_dir
from phemius.voices import get_engine
from phemius.voices.wav import WavJoiner, wav_duration_seconds

log = structlog.get_logger(__name__)

type StopCheck = Callable[[], bool]


def never_stops() -> bool:
    return False


@overload
def import_file(
    path: Path, source: str | None = None, source_id: None = None
) -> StoredVersion: ...
@overload
def import_file(
    path: Path, source: str, source_id: int
) -> StoredVersion | ExcludedItem: ...
def import_file(
    path: Path, source: str | None = None, source_id: int | None = None
) -> StoredVersion | ExcludedItem:
    """Extract, categorize and store a document, or a new version of it.

    `source` identifies the document (the path by default); `source_id` is the
    managed source it came from, if any. An item of that source whose document
    was deleted is not stored.
    """
    text = ingest.extract_text(path)
    if not text.strip():
        raise ValueError(f"No text found in {path.name}")
    source = source or str(path)
    # Skips the model call on an unchanged save; editors save often.
    stored = document_store.find_unchanged(source, text) or _store_analyzed(
        path, source, text, source_id
    )
    if isinstance(stored, ExcludedItem):
        log.info("document_import_excluded", source_id=source_id)
        return stored
    log.info(
        "document_imported",
        document_id=stored.document_id,
        version=stored.version,
        outcome=stored.outcome,
    )
    return stored


def _store_analyzed(
    path: Path, source: str, text: str, source_id: int | None
) -> StoredVersion | ExcludedItem:
    title = ingest.guess_title(text, path.stem)
    analysis = agent.analyze(title, text)
    document = NewDocument(title=title, source=source, text=text, **analysis)
    return document_store.add_document(document, source_id)


def build_auto_audio(
    document_id: int, skip_not_recommended: bool | None = None
) -> QueuedAudio | None:
    """Queue audio for an automatic import, or None if the import rule skips it.

    With `skip_not_recommended` on (the global setting unless a source's rule
    says otherwise), a document flagged not_recommended is kept but not
    narrated; `build_audio` still narrates it on request.
    """
    document = _get_document(document_id)
    if skip_not_recommended is None:
        skip_not_recommended = load_config().skip_not_recommended
    is_skipped = document["audio_suitability"] == "not_recommended"
    if is_skipped and skip_not_recommended:
        log.info(
            "auto_audio_skipped",
            document_id=document_id,
            version=document["version"],
            reason="not_recommended",
        )
        return None
    return build_audio(document_id)


def build_audio(
    document_id: int, tone: str | None = None, voice: str | None = None
) -> QueuedAudio:
    """Queue audio for a document's latest version in `tone` and `voice`.

    Raises `InvalidInputError` for a voice the configured engine does not offer
    and `VoiceError` when PHEMIUS_TTS or PHEMIUS_VOICE is misconfigured.
    """
    document = _get_document(document_id)
    tone = tone or document["suggested_tone"] or load_config().default_tone
    voice = voices.resolve_voice(voice)
    queued = job_store.enqueue_audio(document_id, document["version_id"], tone, voice)
    log.info("audio_queued", audio_id=queued.audio_id, job_id=queued.job_id)
    queue.notify_workers()
    return queued


def _get_document(document_id: int) -> Document:
    document = document_store.get_document(document_id)
    if document is None:
        raise NotFoundError(f"Document {document_id} not found")
    return document


def write_script(job: ClaimedJob, is_stopping: StopCheck = never_stops) -> bool:
    """The `writing_script` stage. False if the job was cancelled meanwhile.

    Between sections it stops early, recording nothing, when the job is
    cancelled or `is_stopping` turns true.
    """
    source = audio_store.get_script_input(job.audio_id)
    if source is None:
        raise NotFoundError("The document version for this audio no longer exists.")
    script = agent.make_script(
        source.title,
        source.text,
        source.tone,
        source.summary,
        should_continue=lambda: not is_stopping() and job_store.is_current(job),
    )
    if script is None:
        return False
    usage = job_usage(script.usage, load_config())
    log.info(
        "script_usage",
        job_id=job.id,
        sections=len(script.sections),
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=usage.cost_usd,
    )
    return job_store.finish_script(job, script.text, script.sections, usage)


def narrate(job: ClaimedJob, is_stopping: StopCheck = never_stops) -> bool:
    """The `narrating` stage. False if the job was cancelled meanwhile.

    Sections are narrated in order and joined into one WAV with each one's
    start time. Between sections it stops early, keeping only the narrated
    sections for a retry, when the job is cancelled or `is_stopping` turns true.

    The job is done with the WAV, or queued for `converting` when another
    output format is set.
    """
    audio = audio_store.get_audio(job.audio_id)
    if audio is None or not audio["script"] or not audio["voice"]:
        raise NotFoundError("This audio has no script to narrate.")
    sections = audio_store.section_scripts(job.audio_id)
    wav = _narrate_sections(
        job.audio_id,
        sections or [audio["script"]],
        audio["voice"],
        should_continue=lambda: not is_stopping() and job_store.is_current(job),
    )
    if wav is None:
        return False
    is_wav_output = load_config().output_format == "wav"
    save = job_store.finish_audio if is_wav_output else job_store.queue_conversion
    if save(job, wav):
        narration_parts.remove_parts(load_config().audio_dir, job.audio_id)
        return True
    Path(wav.path).unlink(missing_ok=True)
    return False


def convert(job: ClaimedJob, is_stopping: StopCheck = never_stops) -> bool:
    """The `converting` stage. False if the job was cancelled meanwhile.

    A conversion that cannot run keeps the WAV and records why on the audio;
    the job still finishes. The WAV is deleted only once the converted file is
    saved.
    """
    audio = audio_store.get_audio(job.audio_id)
    if audio is None or not audio["path"] or not Path(audio["path"]).is_file():
        raise NotFoundError(
            "The narrated audio file is missing.",
            hint="Retry the job to narrate it again.",
        )
    wav_path = Path(audio["path"])
    conversion = ffmpeg.convert(wav_path, load_config().output_format)
    saved = _audio_file(
        conversion.path,
        conversion.format,
        audio["duration_seconds"],
        conversion_note=conversion.note,
    )
    is_converted = conversion.path != wav_path
    if not job_store.finish_audio(job, saved):
        if is_converted:
            conversion.path.unlink(missing_ok=True)
        return False
    if is_converted:
        wav_path.unlink(missing_ok=True)
    log.info(
        "audio_converted",
        audio_id=job.audio_id,
        format=conversion.format,
        size_bytes=saved.size_bytes,
        is_converted=is_converted,
    )
    return True


def error_text(error: Exception) -> str:
    if isinstance(error, PhemiusError) and error.hint:
        return f"{error.message} {error.hint}"
    return str(error)


def _narrate_sections(
    audio_id: int,
    scripts: list[str],
    voice: str,
    should_continue: Callable[[], bool],
) -> AudioFile | None:
    """The narrated WAV with each section's start, or None if stopped early.

    A one-section script is narrated straight to the file, as before sections.
    Longer ones are narrated to parts (see `narration_parts`) that are kept
    until the audio is saved, so disk use peaks at twice the output.
    """
    config = load_config()
    create_private_dir(config.audio_dir)
    engine = get_engine(config)
    out_path = config.audio_dir / f"{audio_id}.{engine.extension}"
    if len(scripts) == 1:
        engine.synthesize(scripts[0], out_path, voice)
        return _audio_file(out_path, "wav", wav_duration_seconds(out_path), (0.0,))
    folder = narration_parts.parts_dir(config.audio_dir, audio_id)
    parts = narration_parts.narrated_parts(
        engine, folder, scripts, voice, should_continue
    )
    if parts is None:
        return None
    try:
        with WavJoiner(out_path) as joiner:
            for part in parts:
                joiner.append(part)
    except VoiceError:
        # Parts that cannot be joined would fail every retry the same way.
        narration_parts.remove_parts(config.audio_dir, audio_id)
        raise
    return _audio_file(out_path, "wav", joiner.duration_seconds, tuple(joiner.starts))


def _audio_file(
    path: Path,
    audio_format: AudioFormat,
    duration_seconds: float | None,
    chapter_starts: tuple[float, ...] = (),
    conversion_note: str | None = None,
) -> AudioFile:
    return AudioFile(
        str(path),
        audio_format,
        path.stat().st_size,
        duration_seconds,
        conversion_note,
        chapter_starts,
    )
