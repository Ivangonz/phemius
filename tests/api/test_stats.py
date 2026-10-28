import pytest
from fastapi.testclient import TestClient

from phemius.app import create_app
from phemius.services import access
from tests.api.test_access import _bearer
from tests.api.test_docs import _upload_sample, _wait_for_audio


def test_today_counts_a_narrated_document(client: TestClient) -> None:
    uploaded = _upload_sample(client, "deploy-guide.md")
    created = client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    audio = _wait_for_audio(client, created.json()["audio_id"])

    response = client.get("/api/stats/today")

    assert response.status_code == 200
    body = response.json()
    assert (body["scripts_written"], body["audio_files"]) == (1, 1)
    assert body["narration_minutes"] == audio["duration_seconds"] / 60
    assert (body["estimated_cost_usd"], body["unpriced_scripts"]) == (0, 0)


def test_today_is_empty_for_a_new_library(client: TestClient) -> None:
    body = client.get("/api/stats/today", params={"utc_offset_minutes": -480}).json()

    assert body["utc_offset_minutes"] == -480
    assert (body["scripts_written"], body["audio_files"]) == (0, 0)
    assert (body["narration_minutes"], body["estimated_cost_usd"]) == (0, 0)


def test_an_impossible_utc_offset_returns_the_standard_error(
    client: TestClient,
) -> None:
    response = client.get("/api/stats/today", params={"utc_offset_minutes": 900})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "utc_offset_minutes"


def test_network_mode_requires_the_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_ACCESS_MODE", "network")

    with TestClient(create_app()) as network_client:
        rejected = network_client.get("/api/stats/today")
        token = access.regenerate_token()
        accepted = network_client.get("/api/stats/today", headers=_bearer(token))

    assert rejected.status_code == 401
    assert accepted.status_code == 200
