from pathlib import Path

from phemius.store import database
from phemius.store.migrations import MIGRATIONS


def test_database_uses_wal_mode(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")

    with database.transaction() as connection:
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]

    assert mode == "wal"
    assert timeout == database.BUSY_TIMEOUT_MS


def test_migrations_keep_data_across_restarts(isolated_env: Path) -> None:
    db_path = isolated_env / "library.db"
    database.init_database(db_path)
    with database.transaction() as connection:
        connection.execute("INSERT INTO docs (title) VALUES ('Deploy guide')")

    database.init_database(db_path)

    with database.transaction() as connection:
        title = connection.execute("SELECT title FROM docs").fetchone()[0]
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert title == "Deploy guide"
    assert version == len(MIGRATIONS)


def test_failed_transaction_rolls_back(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")

    try:
        with database.transaction() as connection:
            connection.execute("INSERT INTO docs (title) VALUES ('Half written')")
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    with database.transaction() as connection:
        count = connection.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    assert count == 0
