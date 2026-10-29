"""Schema migrations tracked with `PRAGMA user_version`.

Append new migrations to `MIGRATIONS`; never edit one that has shipped. Each runs
inside the caller's transaction, so a failure leaves the library unchanged.
"""

import sqlite3
from collections.abc import Callable
from pathlib import Path

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


_JOB_QUEUE_STATEMENTS = [
    # audio is renamed before jobs exists, so the jobs foreign key is not
    # rewritten to point at legacy_audio.
    "ALTER TABLE audio RENAME TO legacy_audio",
    """
    CREATE TABLE audio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER,
        version_id INTEGER REFERENCES doc_versions (id),
        tone TEXT,
        voice TEXT,
        script TEXT,
        path TEXT,
        created REAL
    )
    """,
    "INSERT INTO audio (id, doc_id, version_id, tone, voice, script, path, created)"
    " SELECT id, doc_id, version_id, tone, voice, script, path, created"
    " FROM legacy_audio",
    """
    CREATE TABLE jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        audio_id INTEGER REFERENCES audio (id),
        version_id INTEGER REFERENCES doc_versions (id),
        state TEXT NOT NULL,
        stage TEXT NOT NULL,
        progress REAL NOT NULL DEFAULT 0,
        error_message TEXT,
        error_hint TEXT,
        attempts INTEGER NOT NULL DEFAULT 1,
        created REAL NOT NULL,
        started REAL,
        updated REAL NOT NULL,
        finished REAL
    )
    """,
    "CREATE INDEX jobs_pickup ON jobs (state, stage, created)",
    "CREATE INDEX jobs_created ON jobs (created)",
    "CREATE UNIQUE INDEX jobs_audio ON jobs (audio_id)",
    """
    INSERT INTO jobs (type, audio_id, version_id, state, stage, progress,
        error_message, error_hint, created, updated)
    SELECT 'audio', id, version_id,
        CASE WHEN status = 'done' THEN 'done' ELSE 'failed' END,
        CASE WHEN script IS NULL THEN 'writing_script' ELSE 'narrating' END,
        CASE WHEN status = 'done' THEN 1 ELSE 0 END,
        CASE
            WHEN status = 'done' THEN NULL
            WHEN status = 'error' THEN error
            ELSE 'Interrupted by a restart'
        END,
        CASE
            WHEN status IN ('done', 'error') THEN NULL
            ELSE 'Retry the job to generate this audio.'
        END,
        COALESCE(created, 0), COALESCE(created, 0)
    FROM legacy_audio ORDER BY id
    """,
    "DROP TABLE legacy_audio",
    """
    CREATE TABLE queue (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        is_paused INTEGER NOT NULL
    )
    """,
    "INSERT INTO queue (id, is_paused) VALUES (1, 0)",
]


def _add_job_queue(connection: sqlite3.Connection) -> None:
    """Move audio progress into persisted jobs, one per existing audio.

    The audio status and error columns are dropped (by rebuilding the table, as
    older SQLite cannot drop columns) so a job is the only place state lives.
    Unfinished legacy audio was lost by the restart that runs this migration, so
    it becomes a failed job the user can retry rather than a surprise rerun.
    """
    for statement in _JOB_QUEUE_STATEMENTS:
        connection.execute(statement)


_DOCUMENT_LIST_INDEXES = [
    "CREATE INDEX docs_created ON docs (created)",
    "CREATE INDEX doc_versions_category ON doc_versions (category)",
    "CREATE INDEX doc_versions_suggested_tone ON doc_versions (suggested_tone)",
    "CREATE INDEX audio_version ON audio (version_id, created)",
    "CREATE INDEX audio_doc ON audio (doc_id)",
]


def _index_document_list(connection: sqlite3.Connection) -> None:
    # doc_versions (doc_id, number) and jobs (audio_id) are already indexed by
    # their UNIQUE constraints.
    for statement in _DOCUMENT_LIST_INDEXES:
        connection.execute(statement)


# An `.mp4` file came from the old `mp4` output format: AAC audio in the same
# container as `.m4a`, so it is recorded as m4a.
_FORMATS_BY_SUFFIX = {".wav": "wav", ".m4a": "m4a", ".mp4": "m4a", ".mp3": "mp3"}


def _add_audio_format_and_size(connection: sqlite3.Connection) -> None:
    """Record each audio file's format and size, read from existing files."""
    for column in ["format TEXT", "size_bytes INTEGER", "conversion_note TEXT"]:
        connection.execute(f"ALTER TABLE audio ADD COLUMN {column}")
    rows = connection.execute(
        "SELECT id, path FROM audio WHERE path IS NOT NULL"
    ).fetchall()
    connection.executemany(
        "UPDATE audio SET format = ?, size_bytes = ? WHERE id = ?",
        [(*_audio_file_facts(Path(path)), audio_id) for audio_id, path in rows],
    )


def _audio_file_facts(path: Path) -> tuple[str | None, int | None]:
    size_bytes = path.stat().st_size if path.is_file() else None
    return _FORMATS_BY_SUFFIX.get(path.suffix.lower()), size_bytes


def _add_audio_suitability(connection: sqlite3.Connection) -> None:
    # Nullable: versions analyzed before this have no verdict, which reads as
    # unknown rather than a guess made without the analysis.
    for column in [
        "tone_rationale",
        "audio_suitability",
        "suitability_reason",
        "suitability_source",
    ]:
        connection.execute(f"ALTER TABLE doc_versions ADD COLUMN {column} TEXT")


def _add_script_usage_and_audio_duration(connection: sqlite3.Connection) -> None:
    # Nullable: work done before this has unknown usage and length, never a guess.
    for table, column in [
        ("jobs", "input_tokens INTEGER"),
        ("jobs", "output_tokens INTEGER"),
        ("jobs", "cost_usd REAL"),
        ("jobs", "script_written REAL"),
        ("audio", "duration_seconds REAL"),
    ]:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column}")


_SOURCE_STATEMENTS = [
    """
    CREATE TABLE sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        name TEXT NOT NULL,
        config TEXT NOT NULL,
        rules TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'active',
        last_sync REAL,
        error TEXT,
        created REAL NOT NULL,
        updated REAL NOT NULL,
        UNIQUE (kind, config)
    )
    """,
    """
    CREATE TABLE source_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id INTEGER NOT NULL REFERENCES sources (id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        item TEXT,
        doc_id INTEGER,
        detail TEXT,
        created REAL NOT NULL
    )
    """,
    "CREATE INDEX source_activity_created ON source_activity (created)",
    "CREATE INDEX source_activity_source ON source_activity (source_id, item)",
    "ALTER TABLE docs ADD COLUMN source_id INTEGER"
    " REFERENCES sources (id) ON DELETE SET NULL",
    "CREATE INDEX docs_source_id ON docs (source_id)",
]


def _add_sources(connection: sqlite3.Connection) -> None:
    """Managed sources, their activity log, and the source each document came from.

    Existing documents have no source; startup links those inside an adopted
    watched folder. `config` is canonical JSON, so the unique pair stops the same
    folder being added twice. Activity keeps `doc_id` without a foreign key: an
    entry outlives the document it mentions.
    """
    for statement in _SOURCE_STATEMENTS:
        connection.execute(statement)


def _add_audio_sections(connection: sqlite3.Connection) -> None:
    """The sections a script was written in, in order; they go with their audio.

    `audio.script` stays the joined text, so narration and older readers work.
    """
    connection.execute(
        """
        CREATE TABLE audio_sections (
            audio_id INTEGER NOT NULL REFERENCES audio (id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            title TEXT NOT NULL,
            script TEXT NOT NULL,
            PRIMARY KEY (audio_id, position)
        )
        """
    )


MIGRATIONS: list[Migration] = [
    _create_initial_schema,
    _namespace_voice_ids,
    _create_settings_table,
    _create_access_token_table,
    _add_document_versions,
    _add_job_queue,
    _index_document_list,
    _add_audio_format_and_size,
    _add_audio_suitability,
    _add_script_usage_and_audio_duration,
    _add_sources,
    _add_audio_sections,
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
