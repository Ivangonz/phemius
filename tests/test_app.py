import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from phemius.app import create_app
from tests.conftest import LOCAL_URL

INDEX_HTML = "<!doctype html><title>Phemius</title><div id='root'></div>"


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    built = tmp_path / "static"
    (built / "assets").mkdir(parents=True)
    (built / "index.html").write_text(INDEX_HTML)
    (built / "assets" / "app.js").write_text("console.log('phemius')")
    return built


@pytest.fixture
def ui_client(static_dir: Path) -> Iterator[TestClient]:
    with TestClient(
        create_app(static_dir=static_dir), base_url=LOCAL_URL
    ) as test_client:
        yield test_client


def test_ui_is_served_at_root(ui_client: TestClient) -> None:
    response = ui_client.get("/")

    assert response.status_code == 200
    assert "<title>Phemius</title>" in response.text


def test_built_assets_are_served(ui_client: TestClient) -> None:
    response = ui_client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.text == "console.log('phemius')"


def test_unknown_ui_paths_fall_back_to_index(ui_client: TestClient) -> None:
    response = ui_client.get("/sources/github")

    assert response.status_code == 200
    assert "<title>Phemius</title>" in response.text


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_unknown_api_paths_keep_the_error_shape(
    ui_client: TestClient, method: str
) -> None:
    response = ui_client.request(method, "/api/nope")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found", "code": "not_found"}


def test_app_starts_without_a_built_ui(tmp_path: Path) -> None:
    with TestClient(
        create_app(static_dir=tmp_path / "missing"), base_url=LOCAL_URL
    ) as test_client:
        assert test_client.get("/api/health").status_code == 200
        assert test_client.get("/").json()["code"] == "not_found"


def test_startup_tightens_an_open_library_and_warns_once(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Startup reconfigures structlog, which would replace capture_logs.
    monkeypatch.setattr("phemius.app.configure_logging", lambda level: None)
    isolated_env.mkdir()
    os.chmod(isolated_env, 0o755)
    db_path = isolated_env / "library.db"
    db_path.touch()
    os.chmod(db_path, 0o644)

    with capture_logs() as logs, TestClient(create_app()):
        pass

    warnings = [entry for entry in logs if entry["log_level"] == "warning"]
    assert [entry["event"] for entry in warnings] == ["library_permissions_tightened"]
    assert warnings[0]["paths"] == [str(isolated_env), str(db_path)]
    assert stat.S_IMODE(isolated_env.stat().st_mode) == 0o700
    assert stat.S_IMODE(db_path.stat().st_mode) == 0o600


def test_startup_keeps_the_audio_folder_private(isolated_env: Path) -> None:
    with TestClient(create_app()):
        pass

    assert stat.S_IMODE((isolated_env / "audio").stat().st_mode) == 0o700


def test_startup_leaves_the_watched_folder_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    watched = tmp_path / "watched"
    watched.mkdir()
    os.chmod(watched, 0o755)
    monkeypatch.setenv("PHEMIUS_WATCH_DIR", str(watched))

    with TestClient(create_app()):
        pass

    assert stat.S_IMODE(watched.stat().st_mode) == 0o755
