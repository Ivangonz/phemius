"""Import documents, queue their audio and run each audio job stage.

The job runner (`services/runner.py`) calls the stages; it runs a single
narration worker, so synthesis happens one audio at a time.
"""

from pathlib import Path

import structlog

from phemius.config import load_config
from phemius.errors import NotFoundError, PhemiusError
from phemius.services import agent, ffmpeg, ingest, queue, voices
from phemius.store import audio as audio_store
from phemius.store import documents as document_store
from phemius.store import jobs as job_store
from phemius.store.documents import NewDocument, StoredVersion
from phemius.store.jobs import AudioFile, AudioFormat, ClaimedJob, QueuedAudio
from phemius.store.permissions import create_private_dir
from phemius.voices import get_engine

log = structlog.get_logger(__name__)


def import_file(path: Path, source: str | None = None) -> StoredVersion:
    """Extract, categorize and store a document, or a new version of it."""
    text = ingest.extract_text(path)
    if not text.strip():
        raise ValueError(f"No text found in {path.name}")
    source = source or str(path)
    # Skips the model call on an unchanged save; editors save often.
    stored = document_store.find_unchanged(source, text) or _store_analyzed(
        path, source, text
    )
    log.info(
        "document_imported",
        document_id=stored.document_id,
        version=stored.version,
        outcome=stored.outcome,
    )
    return stored


def _store_analyzed(path: Path, source: str, text: str) -> StoredVersion:
    title = ingest.guess_title(text, path.stem)
    analysis = agent.analyze(title, text)
    document = NewDocument(title=title, source=source, text=text, **analysis)
    return document_store.add_document(document)


def build_audio(
    document_id: int, tone: str | None = None, voice: str | None = None
) -> QueuedAudio:
    """Queue audio for a document's latest version in `tone` and `voice`.

    Raises `InvalidInputError` for a voice the configured engine does not offer
    and `VoiceError` when PHEMIUS_TTS or PHEMIUS_VOICE is misconfigured.
    """
    document = document_store.get_document(document_id)
    if document is None:
        raise NotFoundError(f"Document {document_id} not found")
    tone = tone or document["suggested_tone"]
    voice = voices.resolve_voice(voice)
    queued = job_store.enqueue_audio(document_id, document["version_id"], tone, voice)
    log.info("audio_queued", audio_id=queued.audio_id, job_id=queued.job_id)
    queue.notify_workers()
    return queued


def write_script(job: ClaimedJob) -> bool:
    """The `writing_script` stage. False if the job was cancelled meanwhile."""
    source = audio_store.get_script_input(job.audio_id)
    if source is None:
        raise NotFoundError("The document version for this audio no longer exists.")
    script = agent.make_script(source.title, source.text, source.tone)
    return job_store.finish_script(job, script)


def narrate(job: ClaimedJob) -> bool:
    """The `narrating` stage. False if the job was cancelled meanwhile.

    The job is done with the WAV, or queued for `converting` when another
    output format is set.
    """
    audio = audio_store.get_audio(job.audio_id)
    if audio is None or not audio["script"] or not audio["voice"]:
        raise NotFoundError("This audio has no script to narrate.")
    wav_path = _synthesize(job.audio_id, audio["script"], audio["voice"])
    wav = _audio_file(wav_path, "wav")
    is_wav_output = load_config().output_format == "wav"
    save = job_store.finish_audio if is_wav_output else job_store.queue_conversion
    if save(job, wav):
        return True
    wav_path.unlink(missing_ok=True)
    return False


def convert(job: ClaimedJob) -> bool:
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
    saved = _audio_file(conversion.path, conversion.format, conversion.note)
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


def _synthesize(audio_id: int, script: str, voice: str) -> Path:
    config = load_config()
    create_private_dir(config.audio_dir)
    engine = get_engine(config)
    out_path = config.audio_dir / f"{audio_id}.{engine.extension}"
    engine.synthesize(script, out_path, voice)
    return out_path


def _audio_file(
    path: Path, audio_format: AudioFormat, conversion_note: str | None = None
) -> AudioFile:
    return AudioFile(str(path), audio_format, path.stat().st_size, conversion_note)
