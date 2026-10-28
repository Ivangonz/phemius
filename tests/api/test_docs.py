import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from phemius.store import documents as document_store
from phemius.store.documents import NewDocument
from phemius.voices import ENGINES
from tests.models.fakes import FailingScriptModel, FakeScriptModel, UseScriptModel

SAMPLES = Path(__file__).parents[2] / "samples"


def _wait_for_audio(client: TestClient, audio_id: int) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        audio: dict[str, Any] = client.get(f"/api/audio/{audio_id}").json()
        if audio["status"] in {"done", "failed", "cancelled"}:
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
    assert audio["voice"] == "stub:silent"
    assert audio["script"]
    assert audio_file.status_code == 200
    assert audio_file.headers["content-type"] == "audio/wav"
    assert (audio["format"], audio["conversion_note"]) == ("wav", None)
    assert audio["size_bytes"] == len(audio_file.content)


def test_reuploading_same_content_is_a_duplicate(client: TestClient) -> None:
    first = _upload_sample(client, "standup-notes.md")
    second = _upload_sample(client, "standup-notes.md")

    assert second == {**first, "duplicate": True}
    assert client.get("/api/docs").json()["total"] == 1


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


def test_unknown_voice_returns_standard_error(client: TestClient) -> None:
    uploaded = _upload_sample(client, "deploy-guide.md")

    response = client.post(
        f"/api/docs/{uploaded['doc_id']}/audio", json={"voice": "af_typo"}
    )

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "invalid_input"
    assert body["errors"][0]["field"] == "voice"


def test_upload_keeps_document_when_voice_engine_is_unknown(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_TTS", "espeak")
    content = (SAMPLES / "deploy-guide.md").read_bytes()

    response = client.post(
        "/api/docs", files=[("files", ("deploy.md", content, "text/markdown"))]
    )

    result = response.json()[0]
    assert response.status_code == 200
    assert result["doc_id"] is not None
    assert f"Set PHEMIUS_TTS to one of: {', '.join(ENGINES)}." in result["error"]


def test_missing_document_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/docs/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document 999 not found", "code": "not_found"}


def test_audio_file_not_ready_returns_hint(client: TestClient) -> None:
    response = client.get("/api/audio/999/file")

    assert response.status_code == 404
    assert response.json()["hint"]


def test_script_model_drives_import_and_audio(
    client: TestClient, use_script_model: UseScriptModel
) -> None:
    use_script_model(FakeScriptModel(script="Welcome to the deploy guide."))
    uploaded = _upload_sample(client, "deploy-guide.md")

    document = client.get(f"/api/docs/{uploaded['doc_id']}").json()
    created = client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    audio = _wait_for_audio(client, created.json()["audio_id"])

    assert document["category"] == "proposal / spec"
    assert document["suggested_tone"] == "podcast"
    assert audio["status"] == "done", audio["error"]
    assert audio["tone"] == "podcast"
    assert audio["script"] == "Welcome to the deploy guide."


def test_failing_script_model_fails_audio_with_hint(
    client: TestClient, use_script_model: UseScriptModel
) -> None:
    uploaded = _upload_sample(client, "deploy-guide.md")
    use_script_model(FailingScriptModel())

    created = client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    audio = _wait_for_audio(client, created.json()["audio_id"])

    assert (audio["status"], audio["stage"]) == ("failed", "writing_script")
    assert (audio["error"], audio["hint"]) == (
        "Provider returned 402.",
        "Add provider credits.",
    )
    assert audio["path"] is None


def _upload_text(client: TestClient, name: str, text: str) -> dict[str, Any]:
    response = client.post(
        "/api/docs",
        params={"auto_audio": "false"},
        files=[("files", (name, text.encode(), "text/markdown"))],
    )
    result: dict[str, Any] = response.json()[0]
    return result


def test_reuploading_changed_file_adds_a_version(client: TestClient) -> None:
    first = _upload_text(client, "guide.md", "# Guide\n\nInstall with pip.")
    second = _upload_text(client, "guide.md", "# Guide\n\nInstall with uv.")

    document = client.get(f"/api/docs/{first['doc_id']}").json()

    assert second["doc_id"] == first["doc_id"]
    assert (first["version"], second["version"]) == (1, 2)
    assert second["duplicate"] is False
    assert document["text"] == "# Guide\n\nInstall with uv."


def test_identical_reupload_is_a_duplicate_without_a_model_call(
    client: TestClient, use_script_model: UseScriptModel
) -> None:
    model = FakeScriptModel()
    use_script_model(model)
    first = _upload_text(client, "guide.md", "# Guide\n\nInstall with pip.")

    again = _upload_text(client, "guide.md", "# Guide\n\nInstall with pip.")

    assert again == {**first, "duplicate": True}
    assert model.analyze_calls == 1


def test_versions_are_listed_newest_first_with_paging(client: TestClient) -> None:
    for text in ["One.", "Two.", "Three."]:
        uploaded = _upload_text(client, "guide.md", text)
    url = f"/api/docs/{uploaded['doc_id']}/versions"

    first_page = client.get(url, params={"limit": 2}).json()
    second_page = client.get(url, params={"limit": 2, "offset": 2}).json()

    assert [item["number"] for item in first_page["items"]] == [3, 2]
    assert [item["number"] for item in second_page["items"]] == [1]
    assert first_page["total"] == 3
    assert (first_page["limit"], second_page["offset"]) == (2, 2)


def test_versions_include_their_audio(client: TestClient) -> None:
    uploaded = _upload_sample(client, "deploy-guide.md")
    created = client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    audio = _wait_for_audio(client, created.json()["audio_id"])

    page = client.get(f"/api/docs/{uploaded['doc_id']}/versions").json()

    [version] = page["items"]
    assert [item["id"] for item in version["audio"]] == [audio["id"]]
    assert page["limit"] == 25


def test_versions_of_missing_document_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/docs/999/versions")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_versions_page_size_is_capped(client: TestClient) -> None:
    uploaded = _upload_text(client, "guide.md", "One.")

    response = client.get(
        f"/api/docs/{uploaded['doc_id']}/versions", params={"limit": 101}
    )

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "limit"


def _add_document(title: str, category: str = "how-to", tone: str = "teacher") -> None:
    document_store.add_document(
        NewDocument(
            title=title,
            source=f"/docs/{title}.md",
            text=f"{title} text.",
            category=category,
            summary="A doc.",
            suggested_tone=tone,
        )
    )


def _listed_titles(client: TestClient, **params: str | int) -> list[str]:
    response = client.get("/api/docs", params=params)
    assert response.status_code == 200, response.json()
    return [item["title"] for item in response.json()["items"]]


def test_document_list_filters_combine(client: TestClient) -> None:
    _add_document("Deploy", category="how-to", tone="teacher")
    _add_document("Roadmap", category="reference", tone="podcast")
    _add_document("Runbook", category="how-to", tone="podcast")

    assert _listed_titles(client, category="how-to") == ["Runbook", "Deploy"]
    assert _listed_titles(client, category="how-to", tone="podcast") == ["Runbook"]
    assert _listed_titles(client, q="DEP", status="no_audio") == ["Deploy"]
    assert _listed_titles(client, status="done") == []


def test_document_list_pages_with_total(client: TestClient) -> None:
    for title in ["A", "B", "C"]:
        _add_document(title)

    page = client.get("/api/docs", params={"limit": 2, "offset": 1}).json()

    assert [item["title"] for item in page["items"]] == ["B", "A"]
    assert (page["total"], page["limit"], page["offset"]) == (3, 2, 1)


def test_document_list_item_is_a_summary(client: TestClient) -> None:
    _add_document("Deploy")

    [item] = client.get("/api/docs").json()["items"]

    assert item["status"] == "no_audio"
    assert item["version"] == 1
    assert item["signature"]
    assert "text" not in item


def test_document_list_orders_by_title(client: TestClient) -> None:
    for title in ["beta", "Alpha"]:
        _add_document(title)

    assert _listed_titles(client, order_by="title") == ["Alpha", "beta"]


def test_document_list_search_treats_percent_literally(client: TestClient) -> None:
    _add_document("100% uptime")
    _add_document("1000 users")

    assert _listed_titles(client, q="0%") == ["100% uptime"]


def test_document_list_page_size_is_capped(client: TestClient) -> None:
    response = client.get("/api/docs", params={"limit": 101})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "limit"


def test_unknown_document_order_returns_standard_validation_error(
    client: TestClient,
) -> None:
    response = client.get("/api/docs", params={"order_by": "text; DROP TABLE docs"})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "validation_error"
    assert [error["field"] for error in body["errors"]] == ["order_by"]
