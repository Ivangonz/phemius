"""Watch a folder: import new or changed files and generate their audio."""

import os
import threading
from pathlib import Path

import structlog
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from phemius.config import load_config
from phemius.services import ingest, pipeline
from phemius.store.documents import StoredVersion

log = structlog.get_logger(__name__)

# Let the writer finish before reading the file.
SETTLE_SECONDS = 1.0


def import_watched_file(path: Path, is_auto_audio: bool) -> None:
    if path.suffix.lower() not in ingest.SUPPORTED or path.name.startswith("."):
        return
    try:
        stored = pipeline.import_file(path)
        if is_auto_audio and _should_build_audio(stored):
            pipeline.build_auto_audio(stored.document_id)
    except Exception as error:  # one bad file must not stop the watcher
        log.warning(
            "watched_file_failed", file=path.name, error_type=type(error).__name__
        )


def _should_build_audio(stored: StoredVersion) -> bool:
    if stored.outcome == "new_version":
        return load_config().watch_on_change == "regenerate"
    return stored.outcome == "created"


class _FolderEventHandler(FileSystemEventHandler):
    def __init__(self, is_auto_audio: bool) -> None:
        self.is_auto_audio = is_auto_audio

    def _schedule_import(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(os.fsdecode(event.src_path))
        timer = threading.Timer(
            SETTLE_SECONDS, import_watched_file, [path, self.is_auto_audio]
        )
        timer.start()

    def on_created(self, event: FileSystemEvent) -> None:
        self._schedule_import(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._schedule_import(event)


def start_watcher(folder: Path, is_auto_audio: bool = True) -> BaseObserver:
    folder.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(_FolderEventHandler(is_auto_audio), str(folder), recursive=True)
    observer.start()
    log.info("folder_watch_started", folder=str(folder))
    threading.Thread(
        target=import_existing_files, args=(folder, is_auto_audio), daemon=True
    ).start()
    return observer


def import_existing_files(folder: Path, is_auto_audio: bool) -> None:
    for path in folder.rglob("*"):
        if path.is_file():
            import_watched_file(path, is_auto_audio)
