import sqlite3
from pathlib import Path

from phemius.store import database
from phemius.store.migrations import MIGRATIONS


def _library_before_namespaced_voices(db_path: Path, voices: list[str | None]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    with connection:
        MIGRATIONS[0](connection)
        connection.execute("PRAGMA user_version=1")
        connection.executemany(
            "INSERT INTO audio (doc_id, voice, status) VALUES (1, ?, 'done')",
            [(voice,) for voice in voices],
        )
    connection.close()


def _stored_voices() -> list[str | None]:
    with database.transaction() as connection:
        rows = connection.execute("SELECT voice FROM audio ORDER BY id").fetchall()
    return [row["voice"] for row in rows]


def test_existing_bare_voice_ids_migrate_to_kokoro_namespace(
    isolated_env: Path,
) -> None:
    db_path = isolated_env / "library.db"
    _library_before_namespaced_voices(db_path, ["af_heart", "bm_george", None])

    database.init_database(db_path)

    assert _stored_voices() == ["kokoro:af_heart", "kokoro:bm_george", None]


def test_voice_migration_leaves_namespaced_ids_alone_on_restart(
    isolated_env: Path,
) -> None:
    db_path = isolated_env / "library.db"
    _library_before_namespaced_voices(db_path, ["af_heart", "stub:silent"])

    database.init_database(db_path)
    database.init_database(db_path)

    assert _stored_voices() == ["kokoro:af_heart", "stub:silent"]
