import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

SAMPLES = Path(__file__).parents[2] / "samples"


def _wait_for_audio(client: TestClient, audio_id: int) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        audio: dict[str, Any] = client.get(f"/api/audio/{audio_id}").json()
        if audio["status"] in {"done", "error"}:
            return audio
        time.sleep(0.05)
    raise AssertionError(f"audio {audio_id} did not finish")


def _upload_sample(client: TestClient, name: str) -> dict[str, Any]:
    content = (SAMPLES / name).read_bytes()
    response = client.post(
        "/api/docs",
        params={"auto_audio": "false"},
        files=[("files", (name, content, "text/markdown"))],
    )
    assert response.status_code == 200
    result: dict[str, Any] = response.json()[0]
    return result


def test_upload_then_generate_audio_with_stub_engine(client: TestClient) -> None:
    uploaded = _upload_sample(client, "deploy-guide.md")

    created = client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    audio = _wait_for_audio(client, created.json()["audio_id"])
    audio_file = client.get(f"/api/audio/{audio['id']}/file")

    assert audio["status"] == "done", audio["error"]
    assert audio["script"]
    assert audio_file.status_code == 200
    assert audio_file.headers["content-type"] == "audio/wav"


def test_reuploading_same_content_is_a_duplicate(client: TestClient) -> None:
    first = _upload_sample(client, "standup-notes.md")
    second = _upload_sample(client, "standup-notes.md")

    assert second == {**first, "duplicate": True}
    assert len(client.get("/api/docs").json()) == 1


def test_upload_reports_unsupported_type(client: TestClient) -> None:
    response = client.post(
        "/api/docs", files=[("files", ("diagram.png", b"\x89PNG", "image/png"))]
    )

    assert response.json()[0]["error"] == "unsupported type .png"


def test_unknown_tone_returns_standard_error(client: TestClient) -> None:
    uploaded = _upload_sample(client, "deploy-guide.md")

    response = client.post(
        f"/api/docs/{uploaded['doc_id']}/audio", json={"tone": "shouty"}
    )

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "invalid_input"
    assert body["errors"][0]["field"] == "tone"


def test_missing_document_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/docs/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document 999 not found", "code": "not_found"}


def test_audio_file_not_ready_returns_hint(client: TestClient) -> None:
    response = client.get("/api/audio/999/file")

    assert response.status_code == 404
    assert response.json()["hint"]
