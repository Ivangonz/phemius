"""Managed sources: add them, watch and sync them, and import what they hold.

The watched folder from `PHEMIUS_WATCH_DIR` or a saved `watch_dir` becomes a
folder source on startup (see `adopt_watch_folder`).
"""

import threading
from collections.abc import Mapping
from functools import partial

import structlog

from phemius import sources as source_kinds
from phemius.config import configured_values, load_config
from phemius.errors import DuplicateSourceError, NotFoundError, PhemiusError
from phemius.services import pipeline
from phemius.sources import Source, SourceItem, Watcher
from phemius.store import sources as source_store
from phemius.store.documents import StoredVersion
from phemius.store.sources import KeptSource, NewSource, StoredSource

log = structlog.get_logger(__name__)

_watchers: dict[int, Watcher] = {}
_watchers_lock = threading.Lock()


def create_source(
    kind: str, config: Mapping[str, object], name: str | None = None
) -> StoredSource:
    """Add a source. Raises `InvalidInputError` for a bad kind or config and
    `DuplicateSourceError` when the same source exists."""
    adapter = source_kinds.get_source(kind, config)
    source_id = source_store.add_source(_new_source(kind, adapter, name))
    if source_id is None:
        raise DuplicateSourceError(
            "This source already exists.",
            hint="Edit the existing source instead.",
            field="config",
        )
    log.info("source_created", source_id=source_id, kind=kind)
    return get_source(source_id)


def _new_source(kind: str, adapter: Source, name: str | None) -> NewSource:
    return NewSource(
        kind=kind,
        name=name or adapter.default_name,
        config=adapter.config,
        key_prefix=adapter.key_prefix,
    )


def get_source(source_id: int) -> StoredSource:
    source = source_store.get_source(source_id)
    if source is None:
        raise NotFoundError(f"Source {source_id} not found")
    return source


def adopt_watch_folder() -> None:
    """Make the configured watched folder a folder source, once.

    An environment folder wins, as every environment variable does: it is
    adopted on each start, which does nothing once its source exists. A saved
    folder is adopted and its setting removed in the same transaction, so a
    source deleted later stays deleted. A saved folder shadowed by the
    environment waits until the variable is unset.
    """
    path = load_config().watch_dir
    if path is None:
        return
    origin = configured_values()["watch_dir"].source
    adapter = source_kinds.get_source("folder", {"path": str(path.absolute())})
    retired_setting = "watch_dir" if origin == "saved" else None
    source_id = source_store.add_source(
        _new_source("folder", adapter, None), retired_setting
    )
    if source_id is not None:
        log.info("watch_folder_adopted", source_id=source_id, origin=origin)


def start_sources() -> None:
    """Adopt the watched folder, then watch and sync every active source."""
    adopt_watch_folder()
    for source in active_sources():
        _start(source)


def stop_sources() -> None:
    with _watchers_lock:
        watchers = list(_watchers.values())
        _watchers.clear()
    for watcher in watchers:
        watcher.stop()


def active_sources() -> list[StoredSource]:
    return [
        source for source in source_store.all_sources() if source["status"] == "active"
    ]


def _start(source: StoredSource) -> None:
    source_id = source["id"]
    try:
        watcher = _adapter(source).watch(partial(import_item, source_id))
    except (PhemiusError, OSError) as error:
        _record_failure(source_id, error)
        return
    if watcher is not None:
        with _watchers_lock:
            _watchers[source_id] = watcher
    threading.Thread(target=sync_source, args=(source_id,), daemon=True).start()


def sync_source(source_id: int) -> None:
    """Import every item the source holds now. Paused sources are skipped."""
    source = source_store.get_source(source_id)
    if source is None or source["status"] != "active":
        return
    log.info("source_sync_started", source_id=source_id)
    try:
        _adapter(source).sync(partial(import_item, source_id))
    except PhemiusError as error:
        _record_failure(source_id, error)
        return
    source_store.finish_sync(source_id, error=None)
    log.info("source_sync_finished", source_id=source_id)


def import_item(source_id: int, item: SourceItem) -> None:
    """Import one item, unless its source was paused or deleted meanwhile."""
    source = source_store.get_source(source_id)
    if source is None or source["status"] != "active":
        return
    try:
        stored = pipeline.import_file(item.path, item.key, source_id)
        if _should_build_audio(stored):
            pipeline.build_auto_audio(stored.document_id)
    except Exception as error:  # one bad file must not stop the source
        log.warning(
            "source_item_failed",
            source_id=source_id,
            item=item.name,
            error_type=type(error).__name__,
        )


def _should_build_audio(stored: StoredVersion) -> bool:
    if stored.outcome == "new_version":
        return load_config().watch_on_change == "regenerate"
    return stored.outcome == "created"


def find_problem(source: StoredSource) -> PhemiusError | None:
    """Why the source cannot be read now, or None when it can."""
    try:
        _adapter(source).check()
    except PhemiusError as error:
        return error
    return None


def kept_sources() -> list[KeptSource]:
    """This installation's sources, as a restore keeps them."""
    return [
        KeptSource(source, _adapter(source).key_prefix)
        for source in source_store.all_sources()
    ]


def _adapter(source: StoredSource) -> Source:
    return source_kinds.get_source(source["kind"], source["config"])


def _record_failure(source_id: int, error: Exception) -> None:
    source_store.finish_sync(source_id, error=_failure_text(error))
    log.warning(
        "source_sync_failed", source_id=source_id, error_type=type(error).__name__
    )


def _failure_text(error: Exception) -> str:
    if isinstance(error, PhemiusError):
        return pipeline.error_text(error)
    return f"{type(error).__name__}: {error}"
