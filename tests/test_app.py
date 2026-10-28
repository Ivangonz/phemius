from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from phemius.app import create_app

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
    with TestClient(create_app(static_dir=static_dir)) as test_client:
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
    with TestClient(create_app(static_dir=tmp_path / "missing")) as test_client:
        assert test_client.get("/api/health").status_code == 200
        assert test_client.get("/").json()["code"] == "not_found"
