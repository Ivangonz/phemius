"""Managed sources (watched folders today), the documents they hold and their
activity log."""

import json
import sqlite3
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, TypedDict, cast

from phemius.store.database import transaction

type SourceStatus = Literal["active", "paused"]
type ActivityAction = Literal["imported", "updated", "skipped", "failed"]
type UpdateOutcome = Literal["updated", "missing", "duplicate"]

_COLUMNS = "id, kind, name, config, rules, status, last_sync, error, created, updated"


class StoredSource(TypedDict):
    id: int
    kind: str
    name: str
    config: dict[str, object]
    rules: dict[str, object]
    status: SourceStatus
    last_sync: float | None
    error: str | None
    created: float
    updated: float


@dataclass(frozen=True)
class NewSource:
    kind: str
    name: str
    config: Mapping[str, object]
    # Every document key from this source starts with it (see `Source.key_prefix`).
    key_prefix: str
    rules: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceChanges:
    """Fields to change; None leaves one as it is."""

    name: str | None = None
    config: Mapping[str, object] | None = None
    rules: Mapping[str, object] | None = None


class ActivityEntry(TypedDict):
    id: int
    source_id: int
    source_name: str
    action: ActivityAction
    # The item's name within its source; None for the source as a whole.
    item: str | None
    document_id: int | None
    detail: str
    created: float


@dataclass(frozen=True)
class NewActivity:
    source_id: int
    action: ActivityAction
    item: str | None
    detail: str
    document_id: int | None = None


@dataclass(frozen=True)
class SourcePage:
    items: list[StoredSource]
    total: int


@dataclass(frozen=True)
class ActivityPage:
    items: list[ActivityEntry]
    total: int


@dataclass(frozen=True)
class KeptSource:
    """A source carried over a restore, with the prefix that relinks documents."""

    source: StoredSource
    key_prefix: str


def _canonical(value: Mapping[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def add_source(source: NewSource, retired_setting: str | None = None) -> int | None:
    """Store a source and link the documents already imported from it.

    Returns None when a source of the same kind and config exists. A
    `retired_setting` is deleted in the same transaction, so a setting adopted
    as a source is adopted only once.
    """
    now = time.time()
    with transaction(is_immediate=True) as connection:
        cursor = connection.execute(
            "INSERT INTO sources (kind, name, config, rules, created, updated)"
            " VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (kind, config) DO NOTHING",
            (
                source.kind,
                source.name,
                _canonical(source.config),
                _canonical(source.rules),
                now,
                now,
            ),
        )
        source_id = cursor.lastrowid if cursor.rowcount else None
        if source_id is not None:
            _link_documents(connection, source_id, source.key_prefix)
        if retired_setting is not None:
            connection.execute("DELETE FROM settings WHERE key = ?", (retired_setting,))
    return source_id


def _link_documents(
    connection: sqlite3.Connection, source_id: int, key_prefix: str
) -> None:
    connection.execute(
        "UPDATE docs SET source_id = ?"
        " WHERE source_id IS NULL AND substr(source, 1, ?) = ?",
        (source_id, len(key_prefix), key_prefix),
    )


def get_source(source_id: int) -> StoredSource | None:
    with transaction() as connection:
        row = connection.execute(
            f"SELECT {_COLUMNS} FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
    return _stored(row) if row else None


def all_sources() -> list[StoredSource]:
    with transaction() as connection:
        rows = connection.execute(f"SELECT {_COLUMNS} FROM sources ORDER BY id")
        return [_stored(row) for row in rows]


def list_sources(limit: int, offset: int) -> SourcePage:
    """One page of sources in the order they were added."""
    with transaction() as connection:
        total: int = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        rows = connection.execute(
            f"SELECT {_COLUMNS} FROM sources ORDER BY created, id LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return SourcePage([_stored(row) for row in rows], total)


def _stored(row: sqlite3.Row) -> StoredSource:
    values = dict(row)
    values["config"] = json.loads(values["config"])
    values["rules"] = json.loads(values["rules"])
    return cast(StoredSource, values)


def finish_sync(source_id: int, error: str | None) -> None:
    """Record a sync: a success clears the error, a failure keeps the last success."""
    with transaction() as connection:
        if error is None:
            connection.execute(
                "UPDATE sources SET last_sync = ?, error = NULL WHERE id = ?",
                (time.time(), source_id),
            )
        else:
            connection.execute(
                "UPDATE sources SET error = ? WHERE id = ?", (error, source_id)
            )


def update_source(source_id: int, changes: SourceChanges) -> UpdateOutcome:
    columns = {
        "name": changes.name,
        "config": None if changes.config is None else _canonical(changes.config),
        "rules": None if changes.rules is None else _canonical(changes.rules),
    }
    changed = {column: value for column, value in columns.items() if value is not None}
    assignments = ", ".join(f"{column} = ?" for column in [*changed, "updated"])
    try:
        with transaction() as connection:
            cursor = connection.execute(
                f"UPDATE sources SET {assignments} WHERE id = ?",
                (*changed.values(), time.time(), source_id),
            )
    except sqlite3.IntegrityError:
        return "duplicate"
    return "updated" if cursor.rowcount else "missing"


def set_status(source_id: int, status: SourceStatus) -> bool:
    with transaction() as connection:
        cursor = connection.execute(
            "UPDATE sources SET status = ?, updated = ? WHERE id = ?",
            (status, time.time(), source_id),
        )
    return cursor.rowcount > 0


def delete_source(source_id: int) -> bool:
    """Delete a source and its activity. Its documents stay, with no source."""
    with transaction() as connection:
        cursor = connection.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    return cursor.rowcount > 0


def record_activity(activity: NewActivity) -> None:
    """Add an entry, unless a skip or failure repeats the item's latest entry.

    Every sync meets the same unreadable file or left-out type again; one entry
    says so until something changes. An entry for a source deleted meanwhile
    is dropped.
    """
    with transaction(is_immediate=True) as connection:
        is_repeatable = activity.action in ("skipped", "failed")
        if is_repeatable and _repeats_latest(connection, activity):
            return
        connection.execute(
            "INSERT INTO source_activity"
            " (source_id, action, item, doc_id, detail, created)"
            " SELECT ?, ?, ?, ?, ?, ?"
            " WHERE EXISTS (SELECT 1 FROM sources WHERE id = ?)",
            (
                activity.source_id,
                activity.action,
                activity.item,
                activity.document_id,
                activity.detail,
                time.time(),
                activity.source_id,
            ),
        )


def _repeats_latest(connection: sqlite3.Connection, activity: NewActivity) -> bool:
    latest = connection.execute(
        "SELECT action, detail FROM source_activity"
        " WHERE source_id = ? AND item IS ? ORDER BY id DESC LIMIT 1",
        (activity.source_id, activity.item),
    ).fetchone()
    return latest is not None and tuple(latest) == (activity.action, activity.detail)


def exclude_items(
    connection: sqlite3.Connection, source_id: int, keys: Sequence[str]
) -> None:
    """Keep a source's items out of later syncs, on the caller's transaction."""
    now = time.time()
    connection.executemany(
        "INSERT INTO source_exclusions (source_id, item_key, created)"
        " VALUES (?, ?, ?) ON CONFLICT (source_id, item_key) DO NOTHING",
        [(source_id, key, now) for key in keys],
    )


def is_excluded(source_id: int, key: str) -> bool:
    with transaction() as connection:
        return is_excluded_on(connection, source_id, key)


def is_excluded_on(connection: sqlite3.Connection, source_id: int, key: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM source_exclusions WHERE source_id = ? AND item_key = ?",
        (source_id, key),
    ).fetchone()
    return row is not None


def list_activity(source_id: int | None, limit: int, offset: int) -> ActivityPage:
    """One page of activity, newest first, for one source or for all."""
    where = "" if source_id is None else "WHERE a.source_id = ?"
    parameters = () if source_id is None else (source_id,)
    with transaction() as connection:
        total: int = connection.execute(
            f"SELECT COUNT(*) FROM source_activity a {where}", parameters
        ).fetchone()[0]
        rows = connection.execute(
            "SELECT a.id, a.source_id, s.name AS source_name, a.action, a.item,"
            " a.doc_id AS document_id, a.detail, a.created"
            f" FROM source_activity a JOIN sources s ON s.id = a.source_id {where}"
            " ORDER BY a.created DESC, a.id DESC LIMIT ? OFFSET ?",
            (*parameters, limit, offset),
        ).fetchall()
    return ActivityPage([cast(ActivityEntry, dict(row)) for row in rows], total)


def replace_sources(connection: sqlite3.Connection, kept: Sequence[KeptSource]) -> None:
    """Swap a restored library's sources for `kept`, on `connection`.

    The restored activity log belonged to the other sources, so it goes too, and
    documents and exclusions are relinked by key prefix: source ids from another
    installation mean nothing here. An exclusion no kept source holds is dropped.
    """
    # SQLite does not enforce column types, and an archive may be tampered with.
    excluded_keys: list[str] = [
        row[0]
        for row in connection.execute(
            "SELECT item_key FROM source_exclusions"
            " WHERE typeof(item_key) = 'text' ORDER BY id"
        )
    ]
    connection.execute("DELETE FROM source_exclusions")
    connection.execute("DELETE FROM source_activity")
    connection.execute("UPDATE docs SET source_id = NULL")
    connection.execute("DELETE FROM sources")
    for item in kept:
        source = item.source
        connection.execute(
            f"INSERT INTO sources ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source["id"],
                source["kind"],
                source["name"],
                _canonical(source["config"]),
                _canonical(source["rules"]),
                source["status"],
                source["last_sync"],
                source["error"],
                source["created"],
                source["updated"],
            ),
        )
        _link_documents(connection, source["id"], item.key_prefix)
        exclude_items(
            connection,
            source["id"],
            [key for key in excluded_keys if key.startswith(item.key_prefix)],
        )
