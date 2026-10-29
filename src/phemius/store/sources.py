"""Managed sources (watched folders today) and the documents they hold."""

import json
import sqlite3
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, TypedDict, cast

from phemius.store.database import transaction

type SourceStatus = Literal["active", "paused"]

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
            "INSERT INTO sources (kind, name, config, created, updated)"
            " VALUES (?, ?, ?, ?, ?) ON CONFLICT (kind, config) DO NOTHING",
            (source.kind, source.name, _canonical(source.config), now, now),
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


def replace_sources(connection: sqlite3.Connection, kept: Sequence[KeptSource]) -> None:
    """Swap a restored library's sources for `kept`, on `connection`.

    The restored activity log belonged to the other sources, so it goes too, and
    documents are relinked by key prefix: source ids from another installation
    mean nothing here.
    """
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
