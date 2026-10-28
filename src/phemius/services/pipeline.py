"""Import documents and generate their audio in background threads."""

import shutil
import subprocess
import threading
from pathlib import Path

import structlog

from phemius.config import load_config
from phemius.errors import NotFoundError, PhemiusError
from phemius.services import agent, ingest, voices
from phemius.store import audio as audio_store
from phemius.store import documents as document_store
from phemius.store.documents import Document, NewDocument
from phemius.store.permissions import create_private_dir
from phemius.voices import get_engine

log = structlog.get_logger(__name__)

# One synthesis at a time; local voice models are heavy.
_synthesis_lock = threading.Lock()

# output format -> (extension, ffmpeg codec arguments)
FORMATS = {
    "m4a": ("m4a", ["-c:a", "aac", "-b:a", "96k"]),
    "mp4": ("mp4", ["-c:a", "aac", "-b:a", "96k"]),
    "mp3": ("mp3", ["-c:a", "libmp3lame", "-b:a", "96k"]),
}


def import_file(path: Path, source: str | None = None) -> tuple[int, bool]:
    """Extract, categorize and store a document. Returns `(document_id, is_created)`."""
    text = ingest.extract_text(path)
    if not text.strip():
        raise ValueError(f"No text found in {path.name}")
    title = ingest.guess_title(text, path.stem)
    analysis = agent.analyze(title, text)
    document = NewDocument(
        title=title, source=source or str(path), text=text, **analysis
    )
    document_id, is_created = document_store.add_document(document)
    log.info("document_imported", document_id=document_id, is_created=is_created)
    return document_id, is_created


def build_audio(
    document_id: int, tone: str | None = None, voice: str | None = None
) -> int:
    """Create an audio record and generate it in a background thread.

    Raises `InvalidInputError` for a voice the configured engine does not offer
    and `VoiceError` when PHEMIUS_TTS or PHEMIUS_VOICE is misconfigured.
    """
    document = document_store.get_document(document_id)
    if document is None:
        raise NotFoundError(f"Document {document_id} not found")
    tone = tone or document["suggested_tone"]
    voice = voices.resolve_voice(voice)
    audio_id = audio_store.create_audio(document_id, tone, voice)
    threading.Thread(
        target=generate_audio, args=(audio_id, document, tone, voice), daemon=True
    ).start()
    return audio_id


def generate_audio(audio_id: int, document: Document, tone: str, voice: str) -> None:
    log.info("audio_started", audio_id=audio_id, document_id=document["id"])
    try:
        audio_store.mark_scripting(audio_id)
        script = agent.make_script(document["title"], document["text"], tone)
        audio_store.save_script(audio_id, script)
        out_path = _synthesize(audio_id, script, voice)
        audio_store.mark_done(audio_id, str(_convert(out_path)))
    except Exception as error:  # stored on the audio row and shown in the UI
        log.warning("audio_failed", audio_id=audio_id, error_type=type(error).__name__)
        audio_store.mark_failed(audio_id, error_text(error))
        return
    log.info("audio_finished", audio_id=audio_id)


def error_text(error: Exception) -> str:
    if isinstance(error, PhemiusError) and error.hint:
        return f"{error.message} {error.hint}"
    return str(error)


def _synthesize(audio_id: int, script: str, voice: str) -> Path:
    config = load_config()
    create_private_dir(config.audio_dir)
    with _synthesis_lock:
        engine = get_engine(config)
        out_path = config.audio_dir / f"{audio_id}.{engine.extension}"
        engine.synthesize(script, out_path, voice)
    return out_path


def _convert(wav_path: Path) -> Path:
    """Convert to the configured format with ffmpeg; keep the WAV if unavailable."""
    output_format = load_config().output_format
    if output_format not in FORMATS or not shutil.which("ffmpeg"):
        return wav_path
    extension, codec = FORMATS[output_format]
    out_path = wav_path.with_suffix(f".{extension}")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), *codec]
        + ["-movflags", "+faststart", str(out_path)],
        check=True,
    )
    wav_path.unlink()
    return out_path
