from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_fails_when_data_folder_is_not_writable(
    client: TestClient, isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_DATA_DIR", str(isolated_env / "missing"))

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["code"] == "unavailable"


def test_unknown_api_route_uses_error_shape(client: TestClient) -> None:
    response = client.get("/api/nope")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found", "code": "not_found"}


def test_validation_errors_list_fields(client: TestClient) -> None:
    response = client.get("/api/docs/not-a-number")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"][0]["field"] == "document_id"
