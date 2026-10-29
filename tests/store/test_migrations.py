import sqlite3
from pathlib import Path

import pytest

from phemius.store import audio as audio_store
from phemius.store import database, migrations
from phemius.store import documents as document_store
from phemius.store import jobs as job_store
from phemius.store import sources as source_store
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


LEGACY_DOCS = [
    (
        1,
        "Deploy guide",
        "deploy.md",
        "hash-1",
        "Ship it.",
        "how-to",
        "Steps.",
        "teacher",
        100.0,
    ),
    (
        2,
        "Notes",
        "notes.md",
        "hash-2",
        "Old notes.",
        "notes",
        "Recap.",
        "podcast",
        200.0,
    ),
    (
        3,
        "Notes",
        "notes.md",
        "hash-3",
        "New notes.",
        "notes",
        "Recap 2.",
        "podcast",
        300.0,
    ),
]
LEGACY_AUDIO = [
    (
        1,
        1,
        "teacher",
        "kokoro:af_heart",
        "Script one.",
        "/audio/1.wav",
        "done",
        None,
        110.0,
    ),
    (2, 3, "podcast", "kokoro:bm_george", None, None, "error", "402", 310.0),
]


def _library_before_versions(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    with connection:
        for migration in MIGRATIONS[:3]:
            migration(connection)
        connection.execute("PRAGMA user_version=3")
        connection.executemany(
            "INSERT INTO docs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", LEGACY_DOCS
        )
        connection.executemany(
            "INSERT INTO audio VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", LEGACY_AUDIO
        )
        connection.execute(
            "INSERT INTO settings VALUES ('output_format', '\"mp3\"', 1.0)"
        )
    connection.close()


def test_existing_documents_become_version_one_without_loss(
    isolated_env: Path,
) -> None:
    db_path = isolated_env / "library.db"
    _library_before_versions(db_path)

    database.init_database(db_path)

    with database.transaction() as connection:
        documents = connection.execute(
            "SELECT d.id, v.title, d.source, v.content_hash, v.text, v.category,"
            " v.summary, v.suggested_tone, d.created, v.number"
            " FROM docs d JOIN doc_versions v ON v.doc_id = d.id ORDER BY d.id"
        ).fetchall()
        audio = connection.execute(
            "SELECT a.id, a.doc_id, a.tone, a.voice, a.script, a.path,"
            " a.created, v.doc_id AS version_doc_id"
            " FROM audio a JOIN doc_versions v ON v.id = a.version_id ORDER BY a.id"
        ).fetchall()
        settings = connection.execute("SELECT key FROM settings").fetchall()
    assert [tuple(row) for row in documents] == [(*doc, 1) for doc in LEGACY_DOCS]
    assert [tuple(row)[:-1] for row in audio] == [
        (*row[:6], row[8]) for row in LEGACY_AUDIO
    ]
    assert [row["version_doc_id"] for row in audio] == [1, 3]
    assert [row["key"] for row in settings] == ["output_format"]


def test_version_migration_keeps_rows_with_missing_values(isolated_env: Path) -> None:
    db_path = isolated_env / "library.db"
    _library_before_versions(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute("INSERT INTO docs (id) VALUES (4)")
        connection.execute("INSERT INTO audio (id, doc_id) VALUES (3, 99)")
    connection.close()

    database.init_database(db_path)

    with database.transaction() as connection:
        bare_versions = connection.execute(
            "SELECT number FROM doc_versions WHERE doc_id = 4"
        ).fetchall()
        orphan = connection.execute(
            "SELECT doc_id, version_id FROM audio WHERE id = 3"
        ).fetchone()
    assert [row["number"] for row in bare_versions] == [1]
    assert tuple(orphan) == (99, None)


def test_failed_migration_leaves_the_library_unchanged(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = isolated_env / "library.db"
    _library_before_versions(db_path)

    def fail(connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(migrations, "MIGRATIONS", [*MIGRATIONS, fail])

    with pytest.raises(sqlite3.OperationalError):
        database.init_database(db_path)

    with sqlite3.connect(db_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        titles = connection.execute("SELECT title FROM docs ORDER BY id").fetchall()
    connection.close()
    assert version == 3
    assert [title for (title,) in titles] == ["Deploy guide", "Notes", "Notes"]


# (id, script, status, error) for audio saved before the job queue existed.
AUDIO_BEFORE_JOBS = [
    (1, "Script.", "done", None),
    (2, None, "error", "Provider returned 402. Add provider credits."),
    (3, None, "scripting", None),
    (4, "Script.", "synthesizing", None),
]


def _library_before_jobs(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    with connection:
        for migration in MIGRATIONS[:5]:
            migration(connection)
        connection.execute("PRAGMA user_version=5")
        connection.execute("INSERT INTO docs (id, source, created) VALUES (1, 'a', 1)")
        connection.execute(
            "INSERT INTO doc_versions (id, doc_id, number, title, text, created)"
            " VALUES (1, 1, 1, 'Guide', 'Install it.', 1)"
        )
        connection.executemany(
            "INSERT INTO audio (id, doc_id, version_id, tone, voice, script, path,"
            " status, error, created) VALUES (?, 1, 1, 'teacher', 'stub:silent',"
            " ?, NULL, ?, ?, 10)",
            AUDIO_BEFORE_JOBS,
        )
    connection.close()


def test_existing_audio_becomes_jobs_and_unfinished_audio_fails(
    isolated_env: Path,
) -> None:
    db_path = isolated_env / "library.db"
    _library_before_jobs(db_path)

    database.init_database(db_path)

    with database.transaction() as connection:
        jobs = connection.execute(
            "SELECT audio_id, version_id, state, stage, progress, error_message,"
            " error_hint IS NOT NULL AS has_hint, attempts FROM jobs ORDER BY id"
        ).fetchall()
        audio_columns = connection.execute("PRAGMA table_info(audio)").fetchall()
    interrupted = "Interrupted by a restart"
    assert [tuple(row) for row in jobs] == [
        (1, 1, "done", "narrating", 1, None, 0, 1),
        (2, 1, "failed", "writing_script", 0, AUDIO_BEFORE_JOBS[1][3], 0, 1),
        (3, 1, "failed", "writing_script", 0, interrupted, 1, 1),
        (4, 1, "failed", "narrating", 0, interrupted, 1, 1),
    ]
    assert {"status", "error"}.isdisjoint(column["name"] for column in audio_columns)
    assert job_store.is_queue_paused() is False


def test_migrated_audio_reads_its_status_from_its_job(isolated_env: Path) -> None:
    db_path = isolated_env / "library.db"
    _library_before_jobs(db_path)

    database.init_database(db_path)

    audio = audio_store.get_audio(2)
    assert audio is not None
    assert (audio["status"], audio["error"], audio["tone"]) == (
        "failed",
        AUDIO_BEFORE_JOBS[1][3],
        "teacher",
    )


def _library_before_audio_formats(db_path: Path, paths: list[str | None]) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    with connection:
        for migration in MIGRATIONS[:7]:
            migration(connection)
        connection.execute("PRAGMA user_version=7")
        connection.executemany(
            "INSERT INTO audio (doc_id, tone, path, created)"
            " VALUES (1, 'teacher', ?, 1)",
            [(path,) for path in paths],
        )
    connection.close()


def test_existing_audio_gets_its_format_and_size_from_the_file(
    isolated_env: Path,
) -> None:
    db_path = isolated_env / "library.db"
    wav_path = isolated_env / "audio" / "1.wav"
    wav_path.parent.mkdir(parents=True)
    wav_path.write_bytes(b"RIFF" + bytes(40))
    missing_mp4 = isolated_env / "audio" / "2.mp4"
    _library_before_audio_formats(
        db_path, [str(wav_path), str(missing_mp4), "3.ogg", None]
    )

    database.init_database(db_path)

    with database.transaction() as connection:
        rows = connection.execute(
            "SELECT format, size_bytes, conversion_note FROM audio ORDER BY id"
        ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("wav", 44, None),
        ("m4a", None, None),
        (None, None, None),
        (None, None, None),
    ]


def test_versions_analyzed_before_suitability_report_it_as_unknown(
    isolated_env: Path,
) -> None:
    db_path = isolated_env / "library.db"
    _library_before_jobs(db_path)
    with sqlite3.connect(db_path) as connection:
        for migration in MIGRATIONS[5:6]:
            migration(connection)
        connection.execute("PRAGMA user_version=6")
    connection.close()

    database.init_database(db_path)

    document = document_store.get_document(1)
    assert document is not None
    assert document["title"] == "Guide"
    assert (
        document["audio_suitability"],
        document["suitability_reason"],
        document["tone_rationale"],
        document["suitability_source"],
    ) == (None, None, None, None)


def test_existing_jobs_and_audio_get_unknown_usage_and_duration(
    isolated_env: Path,
) -> None:
    db_path = isolated_env / "library.db"
    _library_before_jobs(db_path)
    with sqlite3.connect(db_path) as connection:
        for migration in MIGRATIONS[5:9]:
            migration(connection)
        connection.execute("PRAGMA user_version=9")
    connection.close()

    database.init_database(db_path)

    job = job_store.get_job(1)
    audio = audio_store.get_audio(1)
    assert job is not None and audio is not None
    assert (job["state"], audio["script"]) == ("done", "Script.")
    assert (job["input_tokens"], job["output_tokens"], job["cost_usd"]) == (
        None,
        None,
        None,
    )
    assert audio["duration_seconds"] is None


def test_existing_documents_have_no_source_and_sources_start_empty(
    isolated_env: Path,
) -> None:
    db_path = isolated_env / "library.db"
    _library_before_jobs(db_path)
    with sqlite3.connect(db_path) as connection:
        for migration in MIGRATIONS[5:10]:
            migration(connection)
        connection.execute("PRAGMA user_version=10")
    connection.close()

    database.init_database(db_path)

    document = document_store.get_document(1)
    assert document is not None
    assert (document["title"], document["source_id"]) == ("Guide", None)
    assert source_store.all_sources() == []
