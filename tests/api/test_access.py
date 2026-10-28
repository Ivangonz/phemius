from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from phemius.app import create_app
from phemius.errors import PhemiusError
from phemius.services import access
from tests.api.test_docs import _upload_sample, _wait_for_audio


@pytest.fixture
def network_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_ACCESS_MODE", "network")


@pytest.fixture
def anonymous_client(network_mode: None, tmp_path: Path) -> Iterator[TestClient]:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<title>Phemius</title>")
    with TestClient(create_app(static_dir=static_dir)) as test_client:
        yield test_client


@pytest.fixture
def token(anonymous_client: TestClient) -> str:
    return access.regenerate_token()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_local_mode_needs_no_token(client: TestClient) -> None:
    assert client.get("/api/docs").status_code == 200


def test_network_mode_rejects_requests_without_a_token(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.get("/api/docs")

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"


def test_network_mode_accepts_the_bearer_token(
    anonymous_client: TestClient, token: str
) -> None:
    assert anonymous_client.get("/api/docs", headers=_bearer(token)).status_code == 200


def test_network_mode_rejects_a_wrong_token(
    anonymous_client: TestClient, token: str
) -> None:
    response = anonymous_client.get("/api/docs", headers=_bearer("phm_wrong"))

    assert response.status_code == 401


def test_health_and_ui_load_without_a_token(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/api/health").status_code == 200
    assert anonymous_client.get("/").status_code == 200


def test_audio_file_accepts_a_query_string_token(
    anonymous_client: TestClient, token: str
) -> None:
    anonymous_client.headers.update(_bearer(token))
    uploaded = _upload_sample(anonymous_client, "deploy-guide.md")
    created = anonymous_client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    audio = _wait_for_audio(anonymous_client, created.json()["audio_id"])
    del anonymous_client.headers["Authorization"]
    file_url = f"/api/audio/{audio['id']}/file"

    assert anonymous_client.get(file_url).status_code == 401
    assert anonymous_client.get(file_url, params={"token": token}).status_code == 200


def test_query_string_token_is_rejected_outside_audio_files(
    anonymous_client: TestClient, token: str
) -> None:
    response = anonymous_client.get("/api/docs", params={"token": token})

    assert response.status_code == 401


def test_regenerate_returns_a_new_token_and_revokes_the_old(
    anonymous_client: TestClient, token: str
) -> None:
    response = anonymous_client.post("/api/access/token", headers=_bearer(token))
    new_token = response.json()["token"]
    with_old = anonymous_client.get("/api/docs", headers=_bearer(token))
    with_new = anonymous_client.get("/api/docs", headers=_bearer(new_token))

    assert response.status_code == 200
    assert new_token.startswith("phm_")
    assert with_old.status_code == 401
    assert with_new.status_code == 200


def test_regenerate_needs_no_token_in_local_mode(client: TestClient) -> None:
    assert client.post("/api/access/token").status_code == 200


def test_first_network_start_shows_the_token_once(
    network_mode: None, capsys: pytest.CaptureFixture[str]
) -> None:
    with TestClient(create_app()):
        first_output = capsys.readouterr().err
    with TestClient(create_app()):
        second_output = capsys.readouterr().err

    shown = next(word for word in first_output.split() if word.startswith("phm_"))
    assert access.is_valid_token(shown)
    assert "phm_" not in second_output


def test_token_never_appears_in_logs(
    network_mode: None, capsys: pytest.CaptureFixture[str]
) -> None:
    with TestClient(create_app()) as test_client:
        startup = capsys.readouterr()
        started_token = "phm_" + startup.err.split("phm_")[1].split()[0]
        with capture_logs() as logs:
            regenerated = test_client.post(
                "/api/access/token", headers=_bearer(started_token)
            ).json()["token"]
            test_client.get("/api/docs", headers=_bearer(regenerated))
            test_client.get("/api/audio/1/file", params={"token": regenerated})

    assert "access_token_created" in startup.out
    assert started_token not in startup.out
    assert started_token not in str(logs)
    assert regenerated not in str(logs)
    assert any(entry["event"] == "access_token_regenerated" for entry in logs)


ENV_TOKEN = "a-long-env-token-from-compose"


def _first_printed_token(output: str) -> str:
    return "phm_" + output.split("phm_")[1].split()[0]


def test_env_token_replaces_a_generated_token_without_printing(
    network_mode: None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with TestClient(create_app()):
        generated = _first_printed_token(capsys.readouterr().err)
    monkeypatch.setenv("PHEMIUS_ACCESS_TOKEN", ENV_TOKEN)

    with TestClient(create_app()) as test_client:
        startup = capsys.readouterr()
        with capture_logs() as logs:
            with_generated = test_client.get("/api/docs", headers=_bearer(generated))
            with_env = test_client.get("/api/docs", headers=_bearer(ENV_TOKEN))

    assert with_generated.status_code == 401
    assert with_env.status_code == 200
    assert "phm_" not in startup.err
    assert ENV_TOKEN not in startup.out + startup.err + str(logs)


def test_short_env_token_refuses_to_start(
    network_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_ACCESS_TOKEN", "too-short")

    with pytest.raises(PhemiusError) as raised, TestClient(create_app()):
        pass

    assert "PHEMIUS_ACCESS_TOKEN" in raised.value.message
    assert "too-short" not in f"{raised.value.message} {raised.value.hint}"


def test_regenerate_is_refused_while_the_env_token_is_set(
    network_mode: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_ACCESS_TOKEN", ENV_TOKEN)

    with TestClient(create_app(), headers=_bearer(ENV_TOKEN)) as test_client:
        response = test_client.post("/api/access/token")
        still_valid = test_client.get("/api/docs")

    assert response.status_code == 409
    assert response.json()["code"] == "setting_locked"
    assert "PHEMIUS_ACCESS_TOKEN" in response.json()["hint"]
    assert ENV_TOKEN not in response.text
    assert still_valid.status_code == 200
