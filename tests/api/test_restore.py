import io
import json
import sqlite3
import stat
import tempfile
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from phemius.app import create_app
from phemius.services import access, queue
from phemius.services import sources as source_service
from phemius.store import database
from phemius.store import documents as document_store
from phemius.store import settings as settings_store
from phemius.store import sources as source_store
from phemius.store.migrations import MIGRATIONS
from tests.api.test_access import _bearer
from tests.api.test_docs import _upload_sample
from tests.api.test_library import (
    SECRET,
    _download_backup,
    _generate_audio,
    _start_blocked_job,
)
from tests.conftest import LOCAL_URL
from tests.services.test_runner import BlockingScriptModel

type OpenLibrary = Callable[[Path], TestClient]
type ChangeMembers = Callable[[dict[str, bytes]], None]


@pytest.fixture
def open_library(monkeypatch: pytest.MonkeyPatch) -> Iterator[OpenLibrary]:
    """Starts the app on another data folder, as a second installation would."""
    clients: list[TestClient] = []

    def open_at(data_dir: Path) -> TestClient:
        for opened in clients:
            opened.__exit__(None, None, None)
        clients.clear()
        monkeypatch.setenv("PHEMIUS_DATA_DIR", str(data_dir))
        monkeypatch.setattr(database, "_db_path", None)
        clients.append(TestClient(create_app(), base_url=LOCAL_URL).__enter__())
        return clients[-1]

    yield open_at
    for opened in clients:
        opened.__exit__(None, None, None)


def _restore(
    client: TestClient, archive: bytes, path: str = "/api/library/restore"
) -> httpx2.Response:
    return client.post(
        path, files=[("file", ("backup.zip", archive, "application/zip"))]
    )


def _titles(client: TestClient) -> list[str]:
    items = client.get("/api/docs", params={"order_by": "title"}).json()["items"]
    return [item["title"] for item in items]


def _rebuilt(archive: bytes, change: ChangeMembers) -> bytes:
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        members = {name: source.read(name) for name in source.namelist()}
    change(members)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as rebuilt:
        for name, content in members.items():
            rebuilt.writestr(name, content)
    return output.getvalue()


def _with_manifest(**changes: Any) -> ChangeMembers:
    def change(members: dict[str, bytes]) -> None:
        manifest = json.loads(members["manifest.json"])
        members["manifest.json"] = json.dumps({**manifest, **changes}).encode()

    return change


def _with_member(name: str, content: bytes = b"x") -> ChangeMembers:
    def change(members: dict[str, bytes]) -> None:
        members[name] = content

    return change


def _without_member(name: str) -> ChangeMembers:
    def change(members: dict[str, bytes]) -> None:
        del members[name]

    return change


def _flip_a_byte_of_audio(archive: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        info = next(
            item for item in source.infolist() if item.filename.startswith("audio/")
        )
    # Stored audio follows its local header: 30 bytes, then the name and extra.
    offset = info.header_offset
    name_length = int.from_bytes(archive[offset + 26 : offset + 28], "little")
    extra_length = int.from_bytes(archive[offset + 28 : offset + 30], "little")
    data_start = offset + 30 + name_length + extra_length
    tampered = bytearray(archive)
    tampered[data_start + 50] ^= 0xFF
    return bytes(tampered)


@pytest.fixture
def backup_bytes(client: TestClient) -> bytes:
    _generate_audio(client, "deploy-guide.md")
    return _download_backup(client)


def test_round_trip_into_an_empty_data_folder_keeps_documents_and_audio(
    open_library: OpenLibrary, tmp_path: Path
) -> None:
    source = open_library(tmp_path / "first")
    first = _generate_audio(source, "deploy-guide.md")
    second = _generate_audio(source, "standup-notes.md")
    titles = _titles(source)
    original_file = source.get(f"/api/audio/{first['id']}/file").content
    archive = _download_backup(source)

    target = open_library(tmp_path / "second")
    response = _restore(target, archive)

    assert response.status_code == 200
    summary = response.json()
    assert (summary["documents"], summary["audio"], summary["audio_files"]) == (
        2,
        2,
        2,
    )
    assert _titles(target) == titles
    restored = target.get(f"/api/audio/{first['id']}").json()
    assert restored["script"] == first["script"]
    assert restored["section_titles"] == first["section_titles"]
    assert Path(restored["path"]).parent == tmp_path / "second" / "audio"
    assert target.get(f"/api/audio/{first['id']}/file").content == original_file
    assert target.get(f"/api/audio/{second['id']}/file").status_code == 200


def test_restored_files_are_private(open_library: OpenLibrary, tmp_path: Path) -> None:
    source = open_library(tmp_path / "first")
    audio = _generate_audio(source, "deploy-guide.md")
    archive = _download_backup(source)
    target = open_library(tmp_path / "second")

    _restore(target, archive)

    restored = Path(target.get(f"/api/audio/{audio['id']}").json()["path"])
    assert stat.S_IMODE(restored.stat().st_mode) == 0o600
    assert stat.S_IMODE(restored.parent.stat().st_mode) == 0o700


def test_restore_replaces_the_current_library(
    client: TestClient, backup_bytes: bytes
) -> None:
    backed_up_titles = _titles(client)
    _generate_audio(client, "standup-notes.md")

    _restore(client, backup_bytes)

    assert _titles(client) == backed_up_titles
    with database.transaction() as connection:
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


def test_inspect_reports_the_contents_without_changing_anything(
    client: TestClient, backup_bytes: bytes
) -> None:
    _generate_audio(client, "standup-notes.md")
    titles = _titles(client)

    response = _restore(client, backup_bytes, "/api/library/restore/inspect")

    assert response.status_code == 200
    body = response.json()
    assert (body["documents"], body["audio_files"]) == (1, 1)
    assert body["app_version"]
    assert _titles(client) == titles


def test_restore_keeps_this_installations_keys_and_token(
    network_client: TestClient,
) -> None:
    token = access.regenerate_token()
    network_client.headers.update(_bearer(token))
    network_client.patch("/api/settings", json={"elevenlabs_api_key": SECRET})
    archive = _download_backup(network_client)
    network_client.patch("/api/settings", json={"elevenlabs_api_key": "el-newer"})

    response = _restore(network_client, archive)

    assert response.status_code == 200
    assert network_client.get("/api/docs").status_code == 200
    assert settings_store.read_settings()["elevenlabs_api_key"] == "el-newer"


def test_restore_migrates_a_library_from_an_older_version(
    client: TestClient, backup_bytes: bytes, tmp_path: Path
) -> None:
    old_db = tmp_path / "old.db"
    connection = sqlite3.connect(old_db)
    for version, migration in enumerate(MIGRATIONS[:-1], start=1):
        with connection:
            migration(connection)
            connection.execute(f"PRAGMA user_version={version}")
    with connection:
        connection.execute("INSERT INTO docs (source, created) VALUES ('old.md', 1)")
        connection.execute(
            "INSERT INTO doc_versions (doc_id, number, title, content_hash, text,"
            " category, summary, suggested_tone, created)"
            " VALUES (1, 1, 'Old guide', 'abc', 'Text.', 'how-to', 'A guide.',"
            " 'teacher', 1)"
        )
    connection.close()
    archive = _rebuilt(backup_bytes, _without_audio)
    archive = _rebuilt(archive, _with_member("library.db", old_db.read_bytes()))

    response = _restore(client, archive)

    assert response.status_code == 200, response.json()
    assert _titles(client) == ["Old guide"]
    with database.transaction() as migrated:
        version = migrated.execute("PRAGMA user_version").fetchone()[0]
    assert version == len(MIGRATIONS)


def _without_audio(members: dict[str, bytes]) -> None:
    for name in [name for name in members if name.startswith("audio/")]:
        del members[name]


REJECTED_CHANGES: dict[str, ChangeMembers] = {
    "zip_slip_parent": _with_member("../evil.txt"),
    "zip_slip_inside_audio": _with_member("audio/../../evil.txt"),
    "absolute_path": _with_member("/tmp/evil.txt"),
    "nested_audio": _with_member("audio/nested/1.wav"),
    "hidden_audio": _with_member("audio/.hidden"),
    "unknown_member": _with_member("notes.txt"),
    "missing_database": _without_member("library.db"),
    "missing_manifest": _without_member("manifest.json"),
    "unknown_format_version": _with_manifest(format_version=2),
    "other_format": _with_manifest(format="something-else"),
    "broken_manifest": _with_member("manifest.json", b"{not json"),
    "not_a_database": _with_member("library.db", b"not a database"),
}


@pytest.mark.parametrize("change", REJECTED_CHANGES.values(), ids=REJECTED_CHANGES)
def test_invalid_archive_is_rejected_and_the_library_is_untouched(
    client: TestClient,
    backup_bytes: bytes,
    isolated_env: Path,
    tmp_path: Path,
    change: ChangeMembers,
) -> None:
    current = _generate_audio(client, "standup-notes.md")
    titles = _titles(client)

    response = _restore(client, _rebuilt(backup_bytes, change))

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_backup"
    assert response.json()["hint"]
    assert _titles(client) == titles
    assert Path(current["path"]).is_file()
    assert not list(isolated_env.glob(".restore-*"))
    assert not (tmp_path / "evil.txt").exists()


def test_newer_schema_is_rejected(
    client: TestClient, backup_bytes: bytes, tmp_path: Path
) -> None:
    newer_db = tmp_path / "newer.db"
    with zipfile.ZipFile(io.BytesIO(backup_bytes)) as source:
        newer_db.write_bytes(source.read("library.db"))
    connection = sqlite3.connect(newer_db)
    connection.execute(f"PRAGMA user_version={len(MIGRATIONS) + 1}")
    connection.close()

    response = _restore(
        client,
        _rebuilt(backup_bytes, _with_member("library.db", newer_db.read_bytes())),
    )

    assert response.status_code == 400
    assert "newer version" in response.json()["detail"]


@pytest.mark.parametrize(
    "archive",
    [b"not a zip at all", b"PK\x03\x04truncated"],
    ids=["not_zip", "truncated"],
)
def test_damaged_archive_is_rejected(
    client: TestClient, backup_bytes: bytes, archive: bytes
) -> None:
    titles = _titles(client)

    response = _restore(client, archive)

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_backup"
    assert _titles(client) == titles


def test_tampered_audio_is_rejected_and_the_library_is_untouched(
    client: TestClient, backup_bytes: bytes
) -> None:
    _generate_audio(client, "standup-notes.md")
    titles = _titles(client)

    response = _restore(client, _flip_a_byte_of_audio(backup_bytes))

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_backup"
    assert _titles(client) == titles


def test_failed_swap_keeps_the_previous_library(
    client: TestClient,
    backup_bytes: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = _generate_audio(client, "standup-notes.md")
    titles = _titles(client)

    def fail(source: Path) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(database, "replace_with", fail)

    with pytest.raises(sqlite3.OperationalError):
        _restore(client, backup_bytes)

    assert _titles(client) == titles
    assert Path(current["path"]).is_file()


def test_restore_is_refused_while_a_job_runs(
    client: TestClient, backup_bytes: bytes, blocking_model: BlockingScriptModel
) -> None:
    _start_blocked_job(client, blocking_model)

    response = _restore(client, backup_bytes)

    assert response.status_code == 409
    assert response.json()["code"] == "library_busy"


@pytest.mark.parametrize(
    "path", ["/api/library/restore", "/api/library/restore/inspect"]
)
def test_restore_requires_the_token_in_network_mode(
    network_client: TestClient, path: str
) -> None:
    response = _restore(network_client, b"anything", path)

    assert response.status_code == 401


def _with_database_change(sql: str) -> ChangeMembers:
    def change(members: dict[str, bytes]) -> None:
        with tempfile.TemporaryDirectory() as work:
            db_path = Path(work) / "library.db"
            db_path.write_bytes(members["library.db"])
            connection = sqlite3.connect(db_path)
            with connection:
                connection.executescript(sql)
            connection.close()
            members["library.db"] = db_path.read_bytes()

    return change


FOREIGN_SCHEMA_OBJECTS = {
    "trigger_on_settings": "CREATE TRIGGER redirect AFTER INSERT ON settings"
    " BEGIN UPDATE settings SET value = '\"http://attacker.test\"'"
    " WHERE key = 'script_base_url'; END;",
    "trigger_on_audio_sections": "CREATE TRIGGER smuggle AFTER INSERT ON"
    " audio_sections BEGIN UPDATE settings SET value = '\"http://attacker.test\"'"
    " WHERE key = 'script_base_url'; END;",
    "altered_audio_sections": "DROP TABLE audio_sections; CREATE TABLE"
    " audio_sections (audio_id INTEGER, position INTEGER, title TEXT, script TEXT);",
    "view": "CREATE VIEW leak AS SELECT key, value FROM settings;",
    "table": "CREATE TABLE extra (id INTEGER PRIMARY KEY);",
    "index": "CREATE INDEX extra_settings ON settings (updated);",
}


@pytest.mark.parametrize(
    "sql", FOREIGN_SCHEMA_OBJECTS.values(), ids=FOREIGN_SCHEMA_OBJECTS
)
def test_archive_with_foreign_schema_objects_is_rejected(
    client: TestClient, backup_bytes: bytes, sql: str
) -> None:
    client.patch("/api/settings", json={"script_base_url": "http://mine.test/v1"})
    titles = _titles(client)

    response = _restore(client, _rebuilt(backup_bytes, _with_database_change(sql)))

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_backup"
    assert _titles(client) == titles
    with database.transaction() as connection:
        foreign = connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('trigger', 'view')"
        ).fetchall()
    assert foreign == []
    assert settings_store.read_settings()["script_base_url"] == "http://mine.test/v1"


ARCHIVE_ENDPOINTS = {
    "script_base_url": "http://archive.test/v1",
    "openai_speech_base_url": "http://archive.test/speech",
    "ollama_url": "http://archive.test:11434",
    "script_provider": "ollama",
}


def test_restore_keeps_this_installations_endpoints_and_folders(
    client: TestClient, tmp_path: Path
) -> None:
    archive_watch_dir = tmp_path / "their-docs"
    archive_watch_dir.mkdir()
    archive_settings = {**ARCHIVE_ENDPOINTS, "watch_dir": str(archive_watch_dir)}
    assert client.patch("/api/settings", json=archive_settings).status_code == 200
    archive = _download_backup(client)
    mine = {
        "script_base_url": "http://mine.test/v1",
        "openai_speech_base_url": "http://mine.test/speech",
        "ollama_url": "http://mine.test:11434",
        "script_provider": "offline",
        "watch_dir": None,
    }
    assert client.patch("/api/settings", json=mine).status_code == 200

    response = _restore(client, archive)

    assert response.status_code == 200
    restored = settings_store.read_settings()
    assert {key: restored.get(key) for key in mine} == mine


def _folder_with_guide(folder: Path) -> int:
    # Paused, so no running job blocks the backup or the restore.
    queue.pause_queue()
    folder.mkdir()
    (folder / "guide.md").write_text("# Guide\n\nInstall it.")
    source_id: int = source_service.create_source("folder", {"path": str(folder)})["id"]
    source_service.sync_source(source_id)
    return source_id


def _source_ids_of_documents() -> list[int | None]:
    with database.transaction() as connection:
        rows = connection.execute("SELECT id FROM docs ORDER BY id").fetchall()
    documents = [document_store.get_document(row["id"]) for row in rows]
    return [document["source_id"] for document in documents if document]


def test_restore_keeps_this_installations_sources(
    open_library: OpenLibrary, tmp_path: Path
) -> None:
    first = open_library(tmp_path / "first")
    _folder_with_guide(tmp_path / "their-docs")
    archive = _download_backup(first)
    target = open_library(tmp_path / "second")
    mine = _folder_with_guide(tmp_path / "my-docs")

    assert _restore(target, archive).status_code == 200

    assert [source["id"] for source in source_store.all_sources()] == [mine]
    assert _source_ids_of_documents() == [None]


def test_restore_relinks_documents_to_the_sources_they_live_in(
    client: TestClient, tmp_path: Path
) -> None:
    source_id = _folder_with_guide(tmp_path / "docs")
    archive = _download_backup(client)

    assert _restore(client, archive).status_code == 200

    assert _source_ids_of_documents() == [source_id]


def _exclusions() -> list[tuple[int, str]]:
    with database.transaction() as connection:
        rows = connection.execute(
            "SELECT source_id, item_key FROM source_exclusions ORDER BY id"
        ).fetchall()
    return [(row["source_id"], row["item_key"]) for row in rows]


def test_a_deleted_document_stays_deleted_after_a_restore(
    client: TestClient, tmp_path: Path
) -> None:
    source_id = _folder_with_guide(tmp_path / "docs")
    [document_id] = [item["id"] for item in client.get("/api/docs").json()["items"]]
    assert client.delete(f"/api/docs/{document_id}").status_code == 204
    archive = _download_backup(client)

    assert _restore(client, archive).status_code == 200
    source_service.sync_source(source_id)

    assert _titles(client) == []
    assert _exclusions() == [(source_id, str(tmp_path / "docs" / "guide.md"))]


def test_an_archive_cannot_exclude_items_of_sources_it_does_not_have(
    client: TestClient, tmp_path: Path
) -> None:
    source_id = _folder_with_guide(tmp_path / "docs")
    planted = (
        "INSERT INTO source_exclusions (source_id, item_key, created)"
        f" VALUES ({source_id + 1}, '/elsewhere/guide.md', 0),"
        f" ({source_id}, 42, 'not a time'), ({source_id}, x'00', 0);"
    )
    archive = _rebuilt(_download_backup(client), _with_database_change(planted))

    assert _restore(client, archive).status_code == 200

    assert _exclusions() == []


def test_restore_pauses_the_queue_so_queued_jobs_wait(client: TestClient) -> None:
    _generate_audio(client, "deploy-guide.md")
    client.post("/api/queue/pause")
    uploaded = _upload_sample(client, "standup-notes.md")
    client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    archive = _rebuilt(
        _download_backup(client),
        _with_database_change("UPDATE queue SET is_paused = 0;"),
    )

    response = _restore(client, archive)

    assert response.status_code == 200
    body = response.json()
    assert (body["is_queue_paused"], body["queued_jobs"]) == (True, 1)
    queue = client.get("/api/queue").json()
    assert queue["is_paused"] is True
    assert [job["state"] for job in queue["items"]] == ["queued", "done"]
