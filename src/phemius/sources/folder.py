"""A folder on this machine: every supported file in it and its subfolders."""

import os
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated

import structlog
from pydantic import AfterValidator, BaseModel, ConfigDict, ValidationError
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from phemius.errors import InvalidInputError, SourceError
from phemius.services import ingest
from phemius.sources.base import ItemHandler, SourceItem

log = structlog.get_logger(__name__)

# Let the writer finish before reading the file.
SETTLE_SECONDS = 1.0


def _absolute(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        raise ValueError("Use an absolute path, such as /home/me/docs or ~/docs.")
    return path


class FolderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    path: Annotated[Path, AfterValidator(_absolute)]


def from_config(config: Mapping[str, object]) -> "FolderSource":
    """Raises `InvalidInputError` for a config that names no absolute folder."""
    try:
        return FolderSource(FolderConfig.model_validate(config).path)
    except ValidationError as error:
        first = error.errors()[0]
        field = ".".join(str(part) for part in ("config", *first["loc"]))
        raise InvalidInputError(
            "The folder source needs an absolute path.",
            field_errors={field: first["msg"]},
        ) from None


class FolderSource:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    @property
    def config(self) -> Mapping[str, object]:
        return {"path": str(self.folder)}

    @property
    def default_name(self) -> str:
        return self.folder.name or str(self.folder)

    @property
    def key_prefix(self) -> str:
        return os.path.join(str(self.folder), "")

    def check(self) -> None:
        if not self.folder.is_dir() or not os.access(self.folder, os.R_OK | os.X_OK):
            raise SourceError(
                f"{self.folder} is not a readable folder.",
                hint="Create the folder or fix its permissions, or edit the source.",
            )

    def sync(self, handle: ItemHandler) -> None:
        self.check()
        for path in sorted(self.folder.rglob("*")):
            item = self.item_at(path)
            if item is not None and path.is_file():
                handle(item)

    def watch(self, handle: ItemHandler) -> "FolderWatcher":
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.check()
        observer = Observer()
        observer.schedule(_EventHandler(self, handle), str(self.folder), recursive=True)
        observer.start()
        log.info("folder_watch_started", folder=str(self.folder))
        return FolderWatcher(observer)

    def item_at(self, path: Path) -> SourceItem | None:
        """The item for a file in this folder, or None if it is not a document.

        Hidden files and folders (`.git`) and unsupported types are not.
        """
        relative = self._relative(path)
        if relative is None or path.suffix.lower() not in ingest.SUPPORTED:
            return None
        if any(part.startswith(".") for part in relative.parts):
            return None
        return SourceItem(str(self.folder / relative), relative.as_posix(), path)

    def _relative(self, path: Path) -> Path | None:
        # Watchers report real paths (macOS: /private/var for /var), and keys
        # must match the ones a sync gives through the configured path.
        for folder in (self.folder, self.folder.resolve()):
            if path.is_relative_to(folder):
                return path.relative_to(folder)
        return None


class FolderWatcher:
    def __init__(self, observer: BaseObserver) -> None:
        self.observer = observer

    def stop(self) -> None:
        self.observer.stop()
        self.observer.join()


class _EventHandler(FileSystemEventHandler):
    def __init__(self, source: FolderSource, handle: ItemHandler) -> None:
        self.source = source
        self.handle = handle

    def _schedule(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        item = self.source.item_at(Path(os.fsdecode(event.src_path)))
        if item is not None:
            threading.Timer(SETTLE_SECONDS, self.handle, [item]).start()

    def on_created(self, event: FileSystemEvent) -> None:
        self._schedule(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._schedule(event)
