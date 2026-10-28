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


def _create_access_token_table(connection: sqlite3.Connection) -> None:
    # One row at most: Phemius has a single access token, stored only as a hash.
    connection.execute(
        """
        CREATE TABLE access_token (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            token_hash TEXT NOT NULL,
            created REAL NOT NULL
        )
        """
    )


_DOCUMENT_VERSION_STATEMENTS = [
    "ALTER TABLE docs RENAME TO legacy_docs",
    """
    CREATE TABLE docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT,
        created REAL
    )
    """,
    "INSERT INTO docs (id, source, created)"
    " SELECT id, source, created FROM legacy_docs",
    "CREATE INDEX docs_source ON docs (source)",
    """
    CREATE TABLE doc_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER NOT NULL REFERENCES docs (id),
        number INTEGER NOT NULL,
        title TEXT,
        content_hash TEXT,
        text TEXT,
        category TEXT,
        summary TEXT,
        suggested_tone TEXT,
        created REAL,
        UNIQUE (doc_id, number)
    )
    """,
    """
    INSERT INTO doc_versions (doc_id, number, title, content_hash, text, category,
        summary, suggested_tone, created)
    SELECT id, 1, title, content_hash, text, category, summary, suggested_tone,
        created
    FROM legacy_docs ORDER BY id
    """,
    "ALTER TABLE audio ADD COLUMN version_id INTEGER REFERENCES doc_versions (id)",
    """
    UPDATE audio SET version_id =
        (SELECT id FROM doc_versions WHERE doc_versions.doc_id = audio.doc_id)
    """,
    "DROP TABLE legacy_docs",
]


def _add_document_versions(connection: sqlite3.Connection) -> None:
    """Split docs into an identity (source) and its versions; each doc becomes v1.

    The docs table is rebuilt because SQLite cannot drop its UNIQUE content_hash
    column. Several legacy docs may share a source (each edit used to create a new
    doc), so source is indexed but not unique; lookups take the newest doc.
    """
    for statement in _DOCUMENT_VERSION_STATEMENTS:
        connection.execute(statement)


MIGRATIONS: list[Migration] = [
    _create_initial_schema,
    _namespace_voice_ids,
    _create_settings_table,
    _create_access_token_table,
    _add_document_versions,
]


def run_migrations(connection: sqlite3.Connection) -> None:
    # sqlite3 opens no implicit transaction before DDL, so without this a failed
    # migration would leave a half-rebuilt table behind.
    connection.execute("BEGIN IMMEDIATE")
    current_version: int = connection.execute("PRAGMA user_version").fetchone()[0]
    for version, migration in enumerate(MIGRATIONS, start=1):
        if version > current_version:
            migration(connection)
            connection.execute(f"PRAGMA user_version={version}")
