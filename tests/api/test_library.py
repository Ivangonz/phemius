import io
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from phemius.app import create_app
from phemius.services import access
from tests.api.test_access import _bearer
from tests.api.test_docs import _upload_sample, _wait_for_audio
from tests.api.test_queue import _wait_for_job
from tests.services.test_runner import BlockingScriptModel

SECRET = "el-very-secret-key"


def _generate_audio(client: TestClient, sample: str) -> dict[str, Any]:
    uploaded = _upload_sample(client, sample)
    created = client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    audio = _wait_for_audio(client, created.json()["audio_id"])
    assert audio["status"] == "done", audio["error"]
    return audio


def _download_backup(client: TestClient) -> bytes:
    response = client.post("/api/library/backup")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    return response.content


def _backup_database(archive_bytes: bytes, tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "backup-library.db"
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        db_path.write_bytes(archive.read("library.db"))
    return sqlite3.connect(db_path)


def _start_blocked_job(client: TestClient, model: BlockingScriptModel) -> None:
    uploaded = _upload_sample(client, "deploy-guide.md")
    client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    assert model.is_writing.wait(timeout=5)


def test_backup_holds_the_database_audio_and_a_manifest(client: TestClient) -> None:
    audio = _generate_audio(client, "deploy-guide.md")

    archive_bytes = _download_backup(client)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        audio_name = f"audio/{Path(audio['path']).name}"
        assert archive.read(audio_name) == Path(audio["path"]).read_bytes()
    assert manifest["format"] == "phemius-backup"
    assert manifest["format_version"] == 1
    assert (manifest["documents"], manifest["audio_files"]) == (1, 1)


def test_backup_leaves_out_api_keys_and_the_access_token(
    client: TestClient, tmp_path: Path
) -> None:
    client.patch("/api/settings", json={"elevenlabs_api_key": SECRET})
    client.patch("/api/settings", json={"output_format": "mp3"})
    access.regenerate_token()

    archive_bytes = _download_backup(client)

    connection = _backup_database(archive_bytes, tmp_path)
    settings = dict(connection.execute("SELECT key, value FROM settings").fetchall())
    token_rows = connection.execute("SELECT * FROM access_token").fetchall()
    assert settings == {"output_format": '"mp3"'}
    assert token_rows == []
    assert SECRET.encode() not in archive_bytes
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert SECRET.encode() not in archive.read("library.db")


def test_backup_does_not_reveal_where_the_library_lives(
    client: TestClient, tmp_path: Path, isolated_env: Path
) -> None:
    _generate_audio(client, "deploy-guide.md")

    connection = _backup_database(_download_backup(client), tmp_path)

    paths = [row[0] for row in connection.execute("SELECT path FROM audio")]
    assert all(path.startswith("audio/") for path in paths)
    assert str(isolated_env) not in "".join(paths)


def test_backup_leaves_no_temporary_files(
    client: TestClient, isolated_env: Path
) -> None:
    _download_backup(client)

    assert not list(isolated_env.glob(".backup-*"))


def test_startup_removes_backups_a_stopped_server_left_behind(
    isolated_env: Path,
) -> None:
    isolated_env.mkdir(parents=True)
    leftover = isolated_env / ".backup-abc123.zip"
    leftover.write_bytes(b"partial")

    with TestClient(create_app()):
        assert not leftover.exists()


def test_delete_all_audio_keeps_documents_and_scripts(client: TestClient) -> None:
    first = _generate_audio(client, "deploy-guide.md")
    second = _generate_audio(client, "standup-notes.md")

    response = client.delete("/api/library/audio")

    assert response.status_code == 200
    assert response.json() == {"deleted_files": 2}
    assert not Path(first["path"]).exists()
    assert not Path(second["path"]).exists()
    kept = client.get(f"/api/audio/{first['id']}").json()
    assert kept["script"] == first["script"]
    assert (kept["path"], kept["status"]) == (None, "cancelled")
    assert kept["error"] == "Audio file deleted"
    assert client.get(f"/api/audio/{first['id']}/file").status_code == 404
    assert client.get("/api/docs").json()["total"] == 2


def test_retrying_after_delete_all_audio_narrates_the_saved_script(
    client: TestClient,
) -> None:
    audio = _generate_audio(client, "deploy-guide.md")
    client.delete("/api/library/audio")

    client.post(f"/api/queue/{audio['job_id']}/retry")

    narrated = _wait_for_audio(client, audio["id"])
    assert narrated["status"] == "done"
    assert narrated["script"] == audio["script"]
    assert Path(narrated["path"]).is_file()


def test_delete_all_audio_removes_files_no_row_points_at(
    client: TestClient, isolated_env: Path
) -> None:
    leftover = isolated_env / "audio" / "99.wav"
    leftover.write_bytes(b"interrupted")

    response = client.delete("/api/library/audio")

    assert response.json() == {"deleted_files": 0}
    assert not leftover.exists()


def test_delete_all_audio_ignores_files_already_missing(client: TestClient) -> None:
    audio = _generate_audio(client, "deploy-guide.md")
    Path(audio["path"]).unlink()

    response = client.delete("/api/library/audio")

    assert response.json() == {"deleted_files": 1}


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/api/library/backup"), ("delete", "/api/library/audio")],
)
def test_library_operations_are_refused_while_a_job_runs(
    client: TestClient, blocking_model: BlockingScriptModel, method: str, path: str
) -> None:
    _start_blocked_job(client, blocking_model)

    response = client.request(method.upper(), path)

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "library_busy"
    assert body["hint"]


def test_delete_all_audio_works_again_once_the_job_finishes(
    client: TestClient, blocking_model: BlockingScriptModel
) -> None:
    _start_blocked_job(client, blocking_model)
    client.delete("/api/library/audio")
    blocking_model.release.set()
    _wait_for_job(client, client.get("/api/queue").json()["items"][0]["id"], "done")

    response = client.delete("/api/library/audio")

    assert response.status_code == 200
    assert response.json() == {"deleted_files": 1}


@pytest.mark.parametrize(
    ("method", "path"),
    [("post", "/api/library/backup"), ("delete", "/api/library/audio")],
)
def test_library_operations_require_the_token_in_network_mode(
    network_client: TestClient, method: str, path: str
) -> None:
    token = access.regenerate_token()

    refused = network_client.request(method.upper(), path)
    allowed = network_client.request(method.upper(), path, headers=_bearer(token))

    assert refused.status_code == 401
    assert allowed.status_code == 200
