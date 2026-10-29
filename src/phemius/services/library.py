"""Whole-library operations other than backup and restore."""

from pathlib import Path

import structlog

from phemius.config import load_config
from phemius.services import maintenance
from phemius.store import jobs as job_store

log = structlog.get_logger(__name__)


def delete_all_audio() -> int:
    """Delete every audio file, keeping documents, versions and scripts.

    Returns how many files the library recorded. Files go after the rows are
    committed, and a file already missing is not an error.
    """
    audio_dir = load_config().audio_dir
    with maintenance.gate.exclusive():
        paths = job_store.clear_audio_files()
        for recorded in paths:
            Path(recorded).unlink(missing_ok=True)
        # Also frees files no row points at, such as a WAV from a narration
        # interrupted by a restart.
        for leftover in audio_dir.glob("*"):
            if leftover.is_file():
                leftover.unlink(missing_ok=True)
    log.info("all_audio_deleted", count=len(paths))
    return len(paths)
