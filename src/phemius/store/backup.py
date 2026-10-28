"""SQL on a library snapshot: a copy of the database outside the live library."""

import sqlite3
from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

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


@contextmanager
def _open(path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
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
        )


def _count(connection: sqlite3.Connection, table: str) -> int:
    count: int = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return count
