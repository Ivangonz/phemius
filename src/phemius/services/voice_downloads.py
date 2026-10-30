"""Download a voice ahead of its first narration, one voice at a time.

Progress lives in memory: a restart forgets it, and the engine's own
`is_installed` still shows which voices finished. Downloads stay out of the
job queue so narration never waits behind one.
"""

import threading
from functools import partial
from typing import Any, Literal

import structlog
from pydantic import BaseModel, ConfigDict

from phemius.config import load_config
from phemius.errors import (
    NotFoundError,
    ServiceUnavailableError,
    VoiceDownloadConflictError,
    VoiceError,
)
from phemius.voices import DownloadableEngine, Voice, get_engine

log = structlog.get_logger(__name__)

STOP_TIMEOUT_SECONDS = 5.0
THREAD_NAME = "voice-download"
RETRY_HINT = "Try again. If it keeps failing, check the server log."

type DownloadState = Literal["downloading", "installed", "failed"]


class DownloadProgress(BaseModel):
    """A voice download started since the server started; bytes done of total."""

    model_config = ConfigDict(frozen=True)

    state: DownloadState
    done: int = 0
    total: int | None = None
    message: str | None = None
    hint: str | None = None


class _DownloadStoppedError(Exception):
    """Raised from the progress callback to end a download between chunks."""


class _Downloads:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.progress: dict[str, DownloadProgress] = {}
        self.active: tuple[str, threading.Thread] | None = None
        self.is_running = False


_downloads = _Downloads()


def start_downloads() -> None:
    """Accept downloads. Progress from an earlier run is forgotten."""
    with _downloads.lock:
        _downloads.progress.clear()
        _downloads.stop.clear()
        _downloads.is_running = True


def stop_downloads() -> None:
    """Stop the running download between chunks and wait for it to clean up."""
    with _downloads.lock:
        _downloads.is_running = False
        active = _downloads.active
    _downloads.stop.set()
    if active is not None:
        active[1].join(STOP_TIMEOUT_SECONDS)


def stop_signal() -> threading.Event:
    """Set once `stop_downloads` begins."""
    return _downloads.stop


def download_progress(voice_id: str) -> DownloadProgress | None:
    with _downloads.lock:
        return _downloads.progress.get(voice_id)


def download_voice(voice_id: str) -> DownloadProgress:
    """Start downloading `voice_id` in the background and return its progress.

    The id must be in the configured engine's catalogue, which alone supplies
    the download URL and file name. Asking again while it runs changes nothing.
    """
    engine = get_engine(load_config())
    voice = _catalogue_voice(engine.voices(), voice_id)
    if not isinstance(engine, DownloadableEngine):
        raise VoiceDownloadConflictError(
            "This voice engine has no voices to download.",
            hint="Its voices need no download; choose one in Settings.",
        )
    if voice.is_installed:
        return DownloadProgress(
            state="installed", done=voice.size_bytes or 0, total=voice.size_bytes
        )
    with _downloads.lock:
        return _start(engine, voice)


def _catalogue_voice(voices: list[Voice], voice_id: str) -> Voice:
    for voice in voices:
        if voice.id == voice_id:
            return voice
    raise NotFoundError(
        "This voice engine has no such voice.", hint="Choose a voice from the list."
    )


def _start(engine: DownloadableEngine, voice: Voice) -> DownloadProgress:
    """Start the download thread; the caller holds the lock."""
    if not _downloads.is_running:
        raise ServiceUnavailableError("Phemius is shutting down.")
    if _downloads.active is not None:
        return _running_download(voice.id)
    progress = DownloadProgress(state="downloading", total=voice.size_bytes)
    thread = threading.Thread(
        target=_run, args=(engine, voice.id), name=THREAD_NAME, daemon=True
    )
    _downloads.progress[voice.id] = progress
    _downloads.active = (voice.id, thread)
    thread.start()
    return progress


def _running_download(voice_id: str) -> DownloadProgress:
    if _downloads.active is None or _downloads.active[0] != voice_id:
        raise VoiceDownloadConflictError(
            "Another voice is downloading.",
            hint="Wait for it to finish, then try again.",
        )
    return _downloads.progress[voice_id]


def _run(engine: DownloadableEngine, voice_id: str) -> None:
    log.info("voice_download_started", voice=voice_id)
    try:
        engine.download(voice_id, partial(_report, voice_id))
    except _DownloadStoppedError:
        _end(voice_id, None)
    except VoiceError as error:
        _end(
            voice_id, {"state": "failed", "message": error.message, "hint": error.hint}
        )
    except Exception as error:  # unrecorded, the download would look stuck forever
        log.error("voice_download_error", error_type=type(error).__name__)
        message = "Could not download the voice."
        _end(voice_id, {"state": "failed", "message": message, "hint": RETRY_HINT})
    else:
        _end(voice_id, {"state": "installed"})


def _report(voice_id: str, done: int, total: int) -> None:
    if _downloads.stop.is_set():
        raise _DownloadStoppedError
    with _downloads.lock:
        current = _downloads.progress[voice_id]
        update = {"done": done, "total": total}
        _downloads.progress[voice_id] = current.model_copy(update=update)


def _end(voice_id: str, outcome: dict[str, Any] | None) -> None:
    """Record how the download ended. A stopped download records nothing."""
    with _downloads.lock:
        _downloads.active = None
        current = _downloads.progress.pop(voice_id)
        if outcome is not None:
            if outcome["state"] == "installed":
                outcome["done"] = current.total or current.done
            _downloads.progress[voice_id] = current.model_copy(update=outcome)
    log.info(
        "voice_download_ended", voice=voice_id, outcome=outcome and outcome["state"]
    )
