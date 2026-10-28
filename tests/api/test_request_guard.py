from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from phemius.app import create_app
from phemius.services import access

SAMPLE_UPLOAD = [("files", ("notes.md", b"# Notes\n\nHello.", "text/markdown"))]


def _upload(client: TestClient, headers: dict[str, str]) -> int:
    response = client.post(
        "/api/docs",
        params={"auto_audio": "false"},
        files=SAMPLE_UPLOAD,
        headers=headers,
    )
    return response.status_code


@pytest.fixture
def network_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("PHEMIUS_ACCESS_MODE", "network")
    with TestClient(create_app(), base_url="http://phemius.example") as client:
        client.headers["Authorization"] = f"Bearer {access.regenerate_token()}"
        yield client


@pytest.mark.parametrize(
    "host", ["evil.example", "evil.example:8000", "192.168.1.20:8000", "localhost."]
)
def test_local_mode_rejects_a_foreign_host(client: TestClient, host: str) -> None:
    response = client.get("/api/docs", headers={"Host": host})

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "untrusted_host"
    assert set(body) == {"detail", "code", "hint"}
    assert "PHEMIUS_ACCESS_MODE=network" in body["hint"]


def test_local_mode_rejects_an_empty_host(client: TestClient) -> None:
    assert client.get("/api/docs", headers={"Host": ""}).status_code == 400


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "LOCALHOST:8000",
        "127.0.0.1",
        "127.0.0.1:8000",
        "127.0.0.2:9000",
        "[::1]",
        "[::1]:8000",
    ],
)
def test_local_mode_accepts_loopback_hosts(client: TestClient, host: str) -> None:
    assert client.get("/api/docs", headers={"Host": host}).status_code == 200


def test_local_mode_guards_the_ui_too() -> None:
    with TestClient(create_app(), base_url="http://evil.example") as client:
        assert client.get("/").status_code == 400


def test_health_is_reachable_with_any_host(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Host": "phemius-container:8000"})

    assert response.status_code == 200


def test_network_mode_accepts_any_host(network_client: TestClient) -> None:
    assert network_client.get("/api/docs").status_code == 200


def test_cross_site_origin_cannot_upload(client: TestClient) -> None:
    status = _upload(client, {"Origin": "http://evil.example"})

    assert status == 403
    assert client.get("/api/docs").json()["total"] == 0


def test_cross_site_rejection_uses_the_error_shape(client: TestClient) -> None:
    response = client.post("/api/checks", headers={"Origin": "http://evil.example"})

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "cross_site_request"
    assert set(body) == {"detail", "code", "hint"}


@pytest.mark.parametrize(
    "origin", ["http://127.0.0.1:8001", "http://localhost:8000", "null"]
)
def test_other_origins_on_this_computer_cannot_upload(
    client: TestClient, origin: str
) -> None:
    assert _upload(client, {"Host": "127.0.0.1:8000", "Origin": origin}) == 403


@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_fetch_metadata_from_another_site_cannot_upload(
    client: TestClient, site: str
) -> None:
    assert _upload(client, {"Sec-Fetch-Site": site}) == 403


def test_same_origin_upload_passes(client: TestClient) -> None:
    headers = {"Host": "localhost:8000", "Origin": "http://localhost:8000"}

    assert _upload(client, headers) == 200


def test_upload_without_origin_passes(client: TestClient) -> None:
    assert _upload(client, {}) == 200


def test_same_origin_fetch_metadata_wins_over_a_rewritten_host(
    network_client: TestClient,
) -> None:
    # A reverse proxy may rewrite Host; the browser's own verdict is trusted.
    headers = {
        "Origin": "https://phemius.home.example",
        "Sec-Fetch-Site": "same-origin",
    }

    assert _upload(network_client, headers) == 200


def test_network_mode_rejects_a_cross_site_upload(network_client: TestClient) -> None:
    assert _upload(network_client, {"Origin": "http://evil.example"}) == 403


def test_cross_site_reads_are_not_blocked(client: TestClient) -> None:
    response = client.get("/api/docs", headers={"Sec-Fetch-Site": "cross-site"})

    assert response.status_code == 200
