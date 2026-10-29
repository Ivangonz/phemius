"""Managed sources: add, edit, pause and delete them, and keep their watchers
and syncs in step. Importing an item lives in `services/source_imports.py`.

The watched folder from `PHEMIUS_WATCH_DIR` or a saved `watch_dir` becomes a
folder source on startup (see `adopt_watch_folder`).
"""

import threading
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Annotated

import structlog
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from phemius import sources as source_kinds
from phemius.config import configured_values, env_override, load_config
from phemius.errors import (
    DuplicateSourceError,
    NotFoundError,
    PhemiusError,
    SettingLockedError,
)
from phemius.services.import_rules import EffectiveRules, ImportRules, merge_rules
from phemius.services.source_imports import failure_text, import_item, rules_of
from phemius.sources import Source, Watcher
from phemius.store import sources as source_store
from phemius.store.sources import (
    ActivityPage,
    KeptSource,
    NewActivity,
    NewSource,
    SourceChanges,
    SourceStatus,
    StoredSource,
)

log = structlog.get_logger(__name__)

type SourceName = Annotated[str, Field(min_length=1, max_length=200)]


class NewSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(description="A registered source kind; today only folder.")
    name: SourceName | None = Field(
        default=None, description="Defaults to the folder's name."
    )
    config: dict[str, JsonValue] = Field(
        description='The kind\'s settings; a folder takes {"path": "/absolute/path"}.'
    )
    rules: ImportRules = ImportRules()


class SourceChange(BaseModel):
    """An edit: only the fields sent change, and rules merge (see `merge_rules`)."""

    model_config = ConfigDict(extra="forbid")

    name: SourceName | None = None
    config: dict[str, JsonValue] | None = None
    rules: ImportRules | None = None


class SourceView(BaseModel):
    id: int
    kind: str
    name: str
    config: dict[str, JsonValue]
    status: SourceStatus
    last_sync: float | None
    error: str | None = Field(description="Why the last sync failed, if it did.")
    created: float
    updated: float
    rules: ImportRules = Field(
        description="This source's own rules; a null rule follows the global setting."
    )
    effective_rules: EffectiveRules
    is_locked: bool = Field(
        description="Set by PHEMIUS_WATCH_DIR: it cannot be moved or deleted."
    )


def describe_source(source: StoredSource) -> SourceView:
    return SourceView.model_validate(
        {
            **source,
            "effective_rules": rules_of(source),
            "is_locked": _is_environment_folder(source),
        }
    )


def list_sources(limit: int, offset: int) -> tuple[list[SourceView], int]:
    page = source_store.list_sources(limit, offset)
    return [describe_source(source) for source in page.items], page.total


def list_activity(source_id: int | None, limit: int, offset: int) -> ActivityPage:
    return source_store.list_activity(source_id, limit, offset)


@dataclass(frozen=True)
class _Sync:
    source_id: int
    stop: threading.Event


class _Background:
    """Running watchers and background syncs. Nothing starts until
    `start_sources` has run, so a CLI command or a test that adds a source
    watches nothing, and `stop_sources` waits for all of it so no import
    outlives the app."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.watchers: dict[int, Watcher] = {}
        self.syncs: dict[threading.Thread, _Sync] = {}
        self.is_running = False


_background = _Background()


def create_source(
    kind: str,
    config: Mapping[str, object],
    name: str | None = None,
    rules: ImportRules | None = None,
) -> StoredSource:
    """Add a source and start it. Raises `InvalidInputError` for a bad kind or
    config and `DuplicateSourceError` when the same source exists."""
    adapter = source_kinds.get_source(kind, config)
    saved_rules = (rules or ImportRules()).model_dump(exclude_none=True)
    source_id = source_store.add_source(_new_source(kind, adapter, name, saved_rules))
    if source_id is None:
        raise _duplicate()
    log.info("source_created", source_id=source_id, kind=kind)
    _start(source_id)
    return get_source(source_id)


def _new_source(
    kind: str,
    adapter: Source,
    name: str | None,
    rules: Mapping[str, object] | None = None,
) -> NewSource:
    return NewSource(
        kind=kind,
        name=name or adapter.default_name,
        config=adapter.config,
        key_prefix=adapter.key_prefix,
        rules=rules or {},
    )


def get_source(source_id: int) -> StoredSource:
    source = source_store.get_source(source_id)
    if source is None:
        raise NotFoundError(f"Source {source_id} not found")
    return source


def update_source(source_id: int, change: SourceChange) -> StoredSource:
    """Rename a source, change its config or merge its rules. A new config
    restarts its watcher and syncs it."""
    source = get_source(source_id)
    config = None
    if change.config is not None:
        _reject_if_environment_folder(source)
        config = source_kinds.get_source(source["kind"], change.config).config
    rules = None
    if change.rules is not None:
        saved = ImportRules.model_validate(source["rules"])
        rules = merge_rules(saved, change.rules).model_dump(exclude_none=True)
    outcome = source_store.update_source(
        source_id, SourceChanges(change.name, config, rules)
    )
    if outcome == "duplicate":
        raise _duplicate()
    log.info(
        "source_updated", source_id=source_id, fields=sorted(change.model_fields_set)
    )
    if config is not None:
        _start(source_id)
    return get_source(source_id)


def pause_source(source_id: int) -> StoredSource:
    """Stop watching and importing until resumed. Documents stay."""
    _set_status(source_id, "paused")
    _stop(source_id)
    return get_source(source_id)


def resume_source(source_id: int) -> StoredSource:
    """Watch again and sync, which imports what changed while paused."""
    _set_status(source_id, "active")
    _start(source_id)
    return get_source(source_id)


def _set_status(source_id: int, status: SourceStatus) -> None:
    if not source_store.set_status(source_id, status):
        raise NotFoundError(f"Source {source_id} not found")
    log.info("source_status_changed", source_id=source_id, status=status)


def delete_source(source_id: int) -> None:
    """Delete a source and its activity. Its documents stay in the library."""
    _reject_if_environment_folder(get_source(source_id))
    _stop(source_id)
    source_store.delete_source(source_id)
    log.info("source_deleted", source_id=source_id)


def request_sync(source_id: int) -> StoredSource:
    """Sync a source in the background; a paused source is not synced."""
    source = get_source(source_id)
    _sync_in_background(source_id)
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
    retired_setting = "watch_dir" if origin == "saved" else None
    source_id = source_store.add_source(
        _new_source("folder", _watch_folder_adapter(path), None), retired_setting
    )
    if source_id is not None:
        log.info("watch_folder_adopted", source_id=source_id, origin=origin)


def _watch_folder_adapter(path: Path) -> Source:
    return source_kinds.get_source("folder", {"path": str(path.absolute())})


def _is_environment_folder(source: StoredSource) -> bool:
    path = load_config().watch_dir
    if env_override("watch_dir") is None or path is None:
        return False
    adopted = ("folder", _watch_folder_adapter(path).config)
    return (source["kind"], source["config"]) == adopted


def _reject_if_environment_folder(source: StoredSource) -> None:
    if _is_environment_folder(source):
        raise SettingLockedError(
            "This folder is set by environment variable PHEMIUS_WATCH_DIR.",
            hint="Unset the variable and restart to move or delete it here.",
        )


def start_sources() -> None:
    """Adopt the watched folder, then watch and sync every active source."""
    adopt_watch_folder()
    _background.is_running = True
    for source in active_sources():
        _start(source["id"])


def stop_sources() -> None:
    """Stop every watcher and sync, then wait for the items being imported.

    A sync stops between items, so shutdown waits at most for one import.
    """
    with _background.lock:
        _background.is_running = False
        watchers = list(_background.watchers.values())
        _background.watchers.clear()
        syncs = dict(_background.syncs)
    for watcher in watchers:
        watcher.stop()
    for sync in syncs.values():
        sync.stop.set()
    for watcher in watchers:
        watcher.join()
    for thread in syncs:
        thread.join()


def is_watching(source_id: int) -> bool:
    with _background.lock:
        return source_id in _background.watchers


def active_sources() -> list[StoredSource]:
    return [
        source for source in source_store.all_sources() if source["status"] == "active"
    ]


def _start(source_id: int) -> None:
    """(Re)start an active source's watcher and sync it in the background."""
    _stop(source_id)
    source = source_store.get_source(source_id)
    if not _background.is_running or source is None or source["status"] != "active":
        return
    try:
        watcher = _adapter(source).watch(partial(import_item, source_id))
    except (PhemiusError, OSError) as error:
        _record_failure(source_id, error)
        return
    if watcher is not None:
        with _background.lock:
            _background.watchers[source_id] = watcher
    _sync_in_background(source_id)


def _stop(source_id: int) -> None:
    """Stop a source's watcher and syncs without waiting for an item being
    imported: this runs in a request, and `import_item` drops work for a
    paused or deleted source."""
    with _background.lock:
        watcher = _background.watchers.pop(source_id, None)
        syncs = [
            sync for sync in _background.syncs.values() if sync.source_id == source_id
        ]
    if watcher is not None:
        watcher.stop()
    for sync in syncs:
        sync.stop.set()


def _sync_in_background(source_id: int) -> None:
    sync = _Sync(source_id, threading.Event())
    thread = threading.Thread(
        target=_run_sync, args=(sync,), name=f"source-sync-{source_id}", daemon=True
    )
    with _background.lock:
        if not _background.is_running:
            return
        _background.syncs[thread] = sync
    thread.start()


def _run_sync(sync: _Sync) -> None:
    try:
        sync_source(sync.source_id, sync.stop)
    finally:
        with _background.lock:
            _background.syncs.pop(threading.current_thread(), None)


def sync_source(source_id: int, stop: threading.Event | None = None) -> None:
    """Import every item the source holds now. Paused sources are skipped.

    A sync ended early by `stop` does not count as a finished sync.
    """
    source = source_store.get_source(source_id)
    if source is None or source["status"] != "active":
        return
    stop = stop or threading.Event()
    log.info("source_sync_started", source_id=source_id)
    try:
        _adapter(source).sync(partial(import_item, source_id), stop)
    except PhemiusError as error:
        _record_failure(source_id, error)
        return
    if stop.is_set():
        log.info("source_sync_stopped", source_id=source_id)
        return
    source_store.finish_sync(source_id, error=None)
    log.info("source_sync_finished", source_id=source_id)


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
    text = failure_text(error)
    source_store.finish_sync(source_id, error=text)
    source_store.record_activity(NewActivity(source_id, "failed", None, text))
    log.warning(
        "source_sync_failed", source_id=source_id, error_type=type(error).__name__
    )


def _duplicate() -> DuplicateSourceError:
    return DuplicateSourceError(
        "This source already exists.",
        hint="Edit the existing source instead.",
        field="config",
    )
