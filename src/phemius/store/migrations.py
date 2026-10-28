"""Schema migrations tracked with `PRAGMA user_version`.

Append new migrations to `MIGRATIONS`; never edit one that has shipped. Each runs
inside the caller's transaction, so a failure leaves the library unchanged.
"""

import sqlite3
from collections.abc import Callable

type Migration = Callable[[sqlite3.Connection], None]


def _create_initial_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            source TEXT,
            content_hash TEXT UNIQUE,
            text TEXT,
            category TEXT,
            summary TEXT,
            suggested_tone TEXT,
            created REAL
        );
        CREATE TABLE audio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER,
            tone TEXT,
            voice TEXT,
            script TEXT,
            path TEXT,
            status TEXT,
            error TEXT,
            created REAL
        );
        """
    )


def _namespace_voice_ids(connection: sqlite3.Connection) -> None:
    # Before voice engines were pluggable, every voice id was a bare Kokoro id.
    connection.execute(
        "UPDATE audio SET voice = 'kokoro:' || voice"
        " WHERE voice IS NOT NULL AND voice != '' AND instr(voice, ':') = 0"
    )


def _create_settings_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated REAL NOT NULL
        )
        """
    )


MIGRATIONS: list[Migration] = [
    _create_initial_schema,
    _namespace_voice_ids,
    _create_settings_table,
]


def run_migrations(connection: sqlite3.Connection) -> None:
    current_version: int = connection.execute("PRAGMA user_version").fetchone()[0]
    for version, migration in enumerate(MIGRATIONS, start=1):
        if version > current_version:
            migration(connection)
            connection.execute(f"PRAGMA user_version={version}")
