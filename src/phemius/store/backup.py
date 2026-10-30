"""SQL on a library snapshot: a copy of the database outside the live library."""

import json
import sqlite3
import time
from collections.abc import Collection, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from phemius.store.jobs import INTERRUPTED_HINT, INTERRUPTED_MESSAGE
from phemius.store.migrations import MIGRATIONS, run_migrations
from phemius.store.sources import KeptSource, replace_sources

# In a snapshot, audio paths are relative to the library folder, so an archive
# neither reveals nor depends on where the library it came from lived.
SNAPSHOT_AUDIO_DIR = "audio"


@dataclass(frozen=True)
class SnapshotAudioFile:
    source: Path
    name: str


@dataclass(frozen=True)
class LibraryCounts:
    schema_version: int
    documents: int
    versions: int
    audio: int
    queued_jobs: int


type SchemaObject = tuple[str, str, str]


@contextmanager
def _open(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    # A snapshot may come from an uploaded archive: its triggers and views must
    # not run functions with side effects.
    connection.execute("PRAGMA trusted_schema=OFF")
    try:
        yield connection
    finally:
        connection.close()


def sanitize_snapshot(
    path: Path, secret_keys: Collection[str]
) -> list[SnapshotAudioFile]:
    """Remove secrets and absolute paths from a snapshot; return its audio files.

    The access token hash belongs to the installation, not the library, so it
    never travels in a snapshot either.
    """
    with _open(path) as connection:
        connection.execute("PRAGMA journal_mode=DELETE")
        with connection:
            connection.executemany(
                "DELETE FROM settings WHERE key = ?", [(key,) for key in secret_keys]
            )
            connection.execute("DELETE FROM access_token")
            audio_files = _make_audio_paths_relative(connection)
        # Deleted rows stay readable in free pages until the file is rebuilt.
        connection.execute("VACUUM")
    return audio_files


def _make_audio_paths_relative(
    connection: sqlite3.Connection,
) -> list[SnapshotAudioFile]:
    rows = connection.execute(
        "SELECT id, path FROM audio WHERE path IS NOT NULL ORDER BY id"
    ).fetchall()
    files = {row["id"]: Path(row["path"]) for row in rows}
    connection.executemany(
        "UPDATE audio SET path = ? WHERE id = ?",
        [
            (f"{SNAPSHOT_AUDIO_DIR}/{path.name}", audio_id)
            for audio_id, path in files.items()
        ],
    )
    return [SnapshotAudioFile(path, path.name) for path in files.values()]


def count_library(path: Path) -> LibraryCounts:
    with _open(path) as connection:
        return LibraryCounts(
            schema_version=connection.execute("PRAGMA user_version").fetchone()[0],
            documents=_count(connection, "docs"),
            versions=_count(connection, "doc_versions"),
            audio=_count(connection, "audio"),
            queued_jobs=connection.execute(
                "SELECT COUNT(*) FROM jobs WHERE state = 'queued'"
            ).fetchone()[0],
        )


def _count(connection: sqlite3.Connection, table: str) -> int:
    count: int = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return count


@dataclass(frozen=True)
class InstallationState:
    """What belongs to this installation rather than its library: kept across a
    restore and never read from an archive."""

    settings: Mapping[str, object]
    setting_keys: Collection[str]
    token_hash: str | None
    sources: Sequence[KeptSource]


def read_schema_version(path: Path) -> int:
    """Raises `sqlite3.DatabaseError` when the file is not an intact database."""
    with _open(path) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise sqlite3.DatabaseError(result)
        version: int = connection.execute("PRAGMA user_version").fetchone()[0]
    return version


def foreign_schema_objects(path: Path, schema_version: int) -> list[str]:
    """Names of schema objects a library migrated to `schema_version` lacks.

    A restored database replaces the live one wholesale, so a crafted archive
    could otherwise bring a trigger or view that rewrites settings on a later
    write. Objects are compared by type, name and SQL with whitespace collapsed.
    """
    with _open(path) as connection:
        archived = _schema_objects(connection)
    reference = sqlite3.connect(":memory:")
    try:
        for migration in MIGRATIONS[:schema_version]:
            with reference:
                migration(reference)
        expected = _schema_objects(reference)
    finally:
        reference.close()
    return sorted({name for _type, name, _sql in archived - expected})


def _schema_objects(connection: sqlite3.Connection) -> set[SchemaObject]:
    rows = connection.execute("SELECT type, name, sql FROM sqlite_master").fetchall()
    return {(row[0], row[1], " ".join((row[2] or "").split())) for row in rows}


def mistyped_columns(path: Path) -> list[str]:
    """`table.column` names holding a value of a type the schema does not declare.

    SQLite stores any value in any column, so a crafted archive could put text
    where the API expects a number. Expected types come from each column's
    declared type, so columns added by later migrations are covered too. The
    snapshot's declared types are only trustworthy once `foreign_schema_objects`
    has found its schema identical to the migrations'.
    """
    with _open(path) as connection:
        return [
            f"{table}.{column}"
            for table, column, allowed in _typed_columns(connection)
            if _holds_other_types(connection, table, column, allowed)
        ]


def _typed_columns(
    connection: sqlite3.Connection,
) -> Iterator[tuple[str, str, list[str]]]:
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    for (table,) in tables:
        columns = connection.execute(
            'SELECT name, type, "notnull" FROM pragma_table_info(?) ORDER BY cid',
            (table,),
        ).fetchall()
        for column in columns:
            allowed = _storage_classes(column["type"])
            if allowed is not None:
                nulls = [] if column["notnull"] else ["null"]
                yield table, column["name"], [*allowed, *nulls]


def _storage_classes(declared_type: str) -> list[str] | None:
    """What `typeof()` may return in a column, by SQLite's affinity rules;
    `None` when any value is acceptable (BLOB or no declared type)."""
    upper = declared_type.upper()
    if "INT" in upper:
        return ["integer"]
    if any(name in upper for name in ("CHAR", "CLOB", "TEXT")):
        return ["text"]
    if upper == "" or "BLOB" in upper:
        return None
    # REAL and NUMERIC affinity: a whole number is a valid float to the API.
    return ["integer", "real"]


def _holds_other_types(
    connection: sqlite3.Connection, table: str, column: str, allowed: list[str]
) -> bool:
    placeholders = ", ".join("?" for _ in allowed)
    row = connection.execute(
        f"SELECT 1 FROM {_quoted(table)}"
        f" WHERE typeof({_quoted(column)}) NOT IN ({placeholders}) LIMIT 1",
        allowed,
    ).fetchone()
    return row is not None


def _quoted(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def prepare_restore(
    path: Path,
    staged_audio_dir: Path,
    audio_dir: Path,
    installation: InstallationState,
    page_size: int,
) -> None:
    """Make an unpacked snapshot ready to replace the live library.

    Migrations see the audio files where they were unpacked; the paths then
    point at the live audio folder they are about to move to.
    """
    with _open(path) as connection:
        connection.execute("PRAGMA journal_mode=DELETE")
        with connection:
            _relocate_audio(connection, staged_audio_dir)
        with connection:
            run_migrations(connection)
        with connection:
            _relocate_audio(connection, audio_dir)
            _fail_running_jobs(connection)
            # Queued work waits for the user, who may not want a restored
            # library to spend model credits on this machine straight away.
            connection.execute("UPDATE queue SET is_paused = 1")
            _apply_installation(connection, installation)
        # A WAL-mode database can only be replaced by one of the same page size.
        connection.execute(f"PRAGMA page_size={int(page_size)}")
        connection.execute("VACUUM")


def _relocate_audio(connection: sqlite3.Connection, audio_dir: Path) -> None:
    rows = connection.execute(
        "SELECT id, path FROM audio WHERE path IS NOT NULL"
    ).fetchall()
    connection.executemany(
        "UPDATE audio SET path = ? WHERE id = ?",
        [(str(audio_dir / Path(row["path"]).name), row["id"]) for row in rows],
    )


def _fail_running_jobs(connection: sqlite3.Connection) -> None:
    now = time.time()
    connection.execute(
        "UPDATE jobs SET state = 'failed', error_message = ?, error_hint = ?,"
        " updated = ?, finished = ? WHERE state = 'running'",
        (INTERRUPTED_MESSAGE, INTERRUPTED_HINT, now, now),
    )


def _apply_installation(
    connection: sqlite3.Connection, installation: InstallationState
) -> None:
    connection.executemany(
        "DELETE FROM settings WHERE key = ?",
        [(key,) for key in installation.setting_keys],
    )
    now = time.time()
    connection.executemany(
        "INSERT INTO settings (key, value, updated) VALUES (?, ?, ?)",
        [(key, json.dumps(value), now) for key, value in installation.settings.items()],
    )
    connection.execute("DELETE FROM access_token")
    if installation.token_hash is not None:
        connection.execute(
            "INSERT INTO access_token (id, token_hash, created) VALUES (1, ?, ?)",
            (installation.token_hash, now),
        )
    replace_sources(connection, installation.sources)
