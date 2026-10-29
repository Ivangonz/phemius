"""Managed sources: add, edit, pause and delete them, and keep their watchers
and syncs in step. Importing an item lives in `services/source_imports.py`.

The watched folder from `PHEMIUS_WATCH_DIR` or a saved `watch_dir` becomes a
folder source on startup (see `adopt_watch_folder`).
"""

import threading
from collections.abc import Mapping
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
from phemius.services.import_rules import ImportRules, merge_rules
from phemius.services.source_imports import failure_text, import_item
from phemius.sources import Source, Watcher
from phemius.store import sources as source_store
from phemius.store.sources import (
    KeptSource,
    NewActivity,
    NewSource,
    SourceChanges,
    SourceStatus,
    StoredSource,
)

log = structlog.get_logger(__name__)

type SourceName = Annotated[str, Field(min_length=1, max_length=200)]


class SourceChange(BaseModel):
    """An edit: only the fields sent change, and rules merge (see `merge_rules`)."""

    model_config = ConfigDict(extra="forbid")

    name: SourceName | None = None
    config: dict[str, JsonValue] | None = None
    rules: ImportRules | None = None


class _Watchers:
    """The running watchers. Sources start only once `start_sources` has run,
    so a CLI command or a test that adds a source watches nothing."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.by_source: dict[int, Watcher] = {}
        self.is_running = False


_watchers = _Watchers()


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
    threading.Thread(target=sync_source, args=(source_id,), daemon=True).start()
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


def _reject_if_environment_folder(source: StoredSource) -> None:
    path = load_config().watch_dir
    if env_override("watch_dir") is None or path is None:
        return
    if (source["kind"], source["config"]) == (
        "folder",
        _watch_folder_adapter(path).config,
    ):
        raise SettingLockedError(
            "This folder is set by environment variable PHEMIUS_WATCH_DIR.",
            hint="Unset the variable and restart to move or delete it here.",
        )


def start_sources() -> None:
    """Adopt the watched folder, then watch and sync every active source."""
    adopt_watch_folder()
    _watchers.is_running = True
    for source in active_sources():
        _start(source["id"])


def stop_sources() -> None:
    with _watchers.lock:
        _watchers.is_running = False
        running = list(_watchers.by_source.values())
        _watchers.by_source.clear()
    for watcher in running:
        watcher.stop()


def is_watching(source_id: int) -> bool:
    with _watchers.lock:
        return source_id in _watchers.by_source


def active_sources() -> list[StoredSource]:
    return [
        source for source in source_store.all_sources() if source["status"] == "active"
    ]


def _start(source_id: int) -> None:
    """(Re)start an active source's watcher and sync it in the background."""
    _stop(source_id)
    source = source_store.get_source(source_id)
    if not _watchers.is_running or source is None or source["status"] != "active":
        return
    try:
        watcher = _adapter(source).watch(partial(import_item, source_id))
    except (PhemiusError, OSError) as error:
        _record_failure(source_id, error)
        return
    if watcher is not None:
        with _watchers.lock:
            _watchers.by_source[source_id] = watcher
    threading.Thread(target=sync_source, args=(source_id,), daemon=True).start()


def _stop(source_id: int) -> None:
    with _watchers.lock:
        watcher = _watchers.by_source.pop(source_id, None)
    if watcher is not None:
        watcher.stop()


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
