"""SQLite connections. WAL mode, a busy timeout and short transactions."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from phemius.store.migrations import run_migrations
from phemius.store.permissions import create_private_dir, create_private_file

BUSY_TIMEOUT_MS = 5000

_db_path: Path | None = None


def init_database(db_path: Path) -> None:
    """Point the store at a database file, enable WAL and apply migrations.

    A new folder and database are created readable by their owner only.
    """
    global _db_path
    create_private_dir(db_path.parent)
    create_private_file(db_path)
    _db_path = db_path
    with transaction() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        run_migrations(connection)


def is_initialized() -> bool:
    return _db_path is not None


def _connect() -> sqlite3.Connection:
    if _db_path is None:
        raise RuntimeError("init_database() must run before the store is used")
    connection = sqlite3.connect(_db_path, timeout=BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """One connection and one transaction: commit on success, roll back on error."""
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def ping() -> None:
    with transaction() as connection:
        connection.execute("SELECT 1").fetchone()
