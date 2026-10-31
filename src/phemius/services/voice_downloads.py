"""Download a voice ahead of its first narration, one voice at a time.

Progress lives in memory: a restart forgets it, and the engine's own
`is_installed` still shows which voices finished. Downloads stay out of the
job queue so narration never waits behind one.
"""

import threading
from functools import partial
from typing import Literal

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


class _Run:
    """The downloads of one server run. A thread keeps the run it started in,
    so one that outlives `stop_downloads` cannot touch the next run's state."""

    def __init__(self, is_running: bool) -> None:
        self.stop = threading.Event()
        self.progress: dict[str, DownloadProgress] = {}
        self.active: tuple[str, threading.Thread] | None = None
        self.is_running = is_running


class _Downloads:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.run = _Run(is_running=False)


_downloads = _Downloads()


def start_downloads() -> None:
    """Accept downloads. Progress from an earlier run is forgotten."""
    with _downloads.lock:
        _downloads.run = _Run(is_running=True)


def stop_downloads() -> None:
    """Stop the running download between chunks and wait for it to clean up."""
    with _downloads.lock:
        run = _downloads.run
        run.is_running = False
        active = run.active
    run.stop.set()
    if active is not None:
        active[1].join(STOP_TIMEOUT_SECONDS)


def stop_signal() -> threading.Event:
    """Set once `stop_downloads` begins for the current run."""
    with _downloads.lock:
        return _downloads.run.stop


def download_progress(voice_id: str) -> DownloadProgress | None:
    with _downloads.lock:
        return _downloads.run.progress.get(voice_id)


def visible_progress(voice: Voice) -> DownloadProgress | None:
    """The progress to show on `voice`.

    A failure is hidden once the voice is installed another way, such as by a
    narration downloading it on first use.
    """
    progress = download_progress(voice.id)
    if progress is not None and progress.state == "failed" and voice.is_installed:
        return None
    return progress


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
        _forget_finished(voice.id)
        return DownloadProgress(
            state="installed", done=voice.size_bytes or 0, total=voice.size_bytes
        )
    with _downloads.lock:
        return _start(_downloads.run, engine, voice)


def _forget_finished(voice_id: str) -> None:
    with _downloads.lock:
        run = _downloads.run
        if run.active is None or run.active[0] != voice_id:
            run.progress.pop(voice_id, None)


def _catalogue_voice(voices: list[Voice], voice_id: str) -> Voice:
    for voice in voices:
        if voice.id == voice_id:
            return voice
    raise NotFoundError(
        "This voice engine has no such voice.", hint="Choose a voice from the list."
    )


def _start(run: _Run, engine: DownloadableEngine, voice: Voice) -> DownloadProgress:
    """Start the download thread; the caller holds the lock."""
    if not run.is_running:
        raise ServiceUnavailableError("Phemius is shutting down.")
    if run.active is not None:
        return _running_download(run, voice.id)
    progress = DownloadProgress(state="downloading", total=voice.size_bytes)
    thread = threading.Thread(
        target=_run, args=(run, engine, voice.id), name=THREAD_NAME, daemon=True
    )
    run.progress[voice.id] = progress
    run.active = (voice.id, thread)
    thread.start()
    return progress


def _running_download(run: _Run, voice_id: str) -> DownloadProgress:
    if run.active is None or run.active[0] != voice_id:
        raise VoiceDownloadConflictError(
            "Another voice is downloading.",
            hint="Wait for it to finish, then try again.",
        )
    return run.progress[voice_id]


def _run(run: _Run, engine: DownloadableEngine, voice_id: str) -> None:
    log.info("voice_download_started", voice=voice_id)
    try:
        engine.download(voice_id, partial(_report, run, voice_id))
    except _DownloadStoppedError:
        _end(run, voice_id, None)
    except VoiceError as error:
        _end(run, voice_id, "failed", error.message, error.hint)
    except Exception as error:  # unrecorded, the download would look stuck forever
        log.error("voice_download_error", error_type=type(error).__name__)
        _end(run, voice_id, "failed", "Could not download the voice.", RETRY_HINT)
    else:
        _end(run, voice_id, "installed")


def _report(run: _Run, voice_id: str, done: int, total: int) -> None:
    if run.stop.is_set():
        raise _DownloadStoppedError
    with _downloads.lock:
        current = run.progress.get(voice_id)
        if current is not None:
            update = {"done": done, "total": total}
            run.progress[voice_id] = current.model_copy(update=update)


def _end(
    run: _Run,
    voice_id: str,
    state: DownloadState | None,
    message: str | None = None,
    hint: str | None = None,
) -> None:
    """Record how the download ended; `None` means it stopped and records nothing."""
    with _downloads.lock:
        run.active = None
        current = run.progress.pop(voice_id, None)
        if current is not None and state is not None:
            done = (
                (current.total or current.done)
                if state == "installed"
                else current.done
            )
            run.progress[voice_id] = DownloadProgress(
                state=state, done=done, total=current.total, message=message, hint=hint
            )
    log.info("voice_download_ended", voice=voice_id, outcome=state or "stopped")
