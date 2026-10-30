import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from phemius.app import create_app
from tests.conftest import LOCAL_URL

MANUAL_AUDIO = {"auto_audio": False}


def _add_folder(client: TestClient, folder: Path, **fields: Any) -> dict[str, Any]:
    folder.mkdir(exist_ok=True)
    response = client.post(
        "/api/sources",
        json={"kind": "folder", "config": {"path": str(folder)}, **fields},
    )
    assert response.status_code == 201, response.text
    source: dict[str, Any] = response.json()
    return source


def _wait_for_activity(client: TestClient, count: int) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        page: dict[str, Any] = client.get("/api/sources/activity").json()
        if page["total"] >= count:
            return page
        time.sleep(0.05)
    raise AssertionError(f"fewer than {count} activity entries")


def _wait_for_first_sync(client: TestClient, source_id: int) -> None:
    # The sync after adding runs in the background and sets last_sync.
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if client.get(f"/api/sources/{source_id}").json()["last_sync"] is not None:
            return
        time.sleep(0.05)
    raise AssertionError("the first sync did not finish")


def test_add_list_and_get_a_folder_source(client: TestClient, tmp_path: Path) -> None:
    added = _add_folder(client, tmp_path / "team-docs")
    _wait_for_first_sync(client, added["id"])

    listed = client.get("/api/sources").json()
    fetched = client.get(f"/api/sources/{added['id']}").json()

    assert (added["kind"], added["name"], added["status"]) == (
        "folder",
        "team-docs",
        "active",
    )
    assert added["config"] == {"path": str(tmp_path / "team-docs")}
    assert added["rules"]["auto_audio"] is None
    assert added["effective_rules"]["auto_audio"] is True
    assert added["is_locked"] is False
    assert (listed["total"], listed["limit"], listed["offset"]) == (1, 25, 0)
    assert listed["items"] == [fetched]


def test_list_is_paged_in_the_order_sources_were_added(
    client: TestClient, tmp_path: Path
) -> None:
    ids = [_add_folder(client, tmp_path / name)["id"] for name in "abc"]

    page = client.get("/api/sources", params={"limit": 2, "offset": 1}).json()

    assert [source["id"] for source in page["items"]] == ids[1:]
    assert page["total"] == 3


def test_a_new_folder_is_imported_and_its_activity_listed(
    client: TestClient, tmp_path: Path
) -> None:
    folder = tmp_path / "docs"
    folder.mkdir()
    (folder / "deploy.md").write_text("# Deploy\n\nShip it.")
    (folder / "notes.md").write_text("# Notes\n\nRecap.")
    source = _add_folder(client, folder, name="Docs", rules=MANUAL_AUDIO)

    _wait_for_activity(client, 2)
    first_page = client.get("/api/sources/activity", params={"limit": 1}).json()
    filtered = client.get(
        "/api/sources/activity", params={"source_id": source["id"]}
    ).json()

    assert first_page["total"] == 2
    [entry] = first_page["items"]
    assert (entry["source_name"], entry["action"]) == ("Docs", "imported")
    assert entry["document_id"] is not None
    assert {item["item"] for item in filtered["items"]} == {"deploy.md", "notes.md"}
    titles = {document["title"] for document in client.get("/api/docs").json()["items"]}
    assert titles == {"Deploy", "Notes"}


def test_edit_renames_and_merges_rules(client: TestClient, tmp_path: Path) -> None:
    source = _add_folder(client, tmp_path / "docs", rules=MANUAL_AUDIO)

    response = client.patch(
        f"/api/sources/{source['id']}",
        json={"name": "Handbook", "rules": {"file_types": ["md", "PDF"]}},
    )

    assert response.status_code == 200
    edited = response.json()
    assert edited["name"] == "Handbook"
    assert edited["rules"]["auto_audio"] is False
    assert edited["rules"]["file_types"] == [".md", ".pdf"]
    assert edited["effective_rules"]["file_types"] == [".md", ".pdf"]


def test_pause_and_resume_report_the_status(client: TestClient, tmp_path: Path) -> None:
    source = _add_folder(client, tmp_path / "docs")

    paused = client.post(f"/api/sources/{source['id']}/pause").json()
    resumed = client.post(f"/api/sources/{source['id']}/resume").json()

    assert (paused["status"], resumed["status"]) == ("paused", "active")


def test_sync_now_is_accepted(client: TestClient, tmp_path: Path) -> None:
    source = _add_folder(client, tmp_path / "docs")

    response = client.post(f"/api/sources/{source['id']}/sync")

    assert response.status_code == 202
    assert response.json()["id"] == source["id"]


def test_delete_removes_the_source(client: TestClient, tmp_path: Path) -> None:
    source = _add_folder(client, tmp_path / "docs")

    response = client.delete(f"/api/sources/{source['id']}")

    assert response.status_code == 204
    assert client.get(f"/api/sources/{source['id']}").status_code == 404


@pytest.mark.parametrize(
    ("body", "status", "code", "field"),
    [
        (
            {"kind": "folder", "config": {"path": "docs"}},
            400,
            "invalid_input",
            "config.path",
        ),
        ({"kind": "folder", "config": {}}, 400, "invalid_input", "config.path"),
        ({"kind": "ftp", "config": {}}, 400, "invalid_input", "kind"),
        (
            {
                "kind": "folder",
                "config": {"path": "/docs"},
                "rules": {"file_types": [".exe"]},
            },
            422,
            "validation_error",
            "rules.file_types",
        ),
        (
            {"kind": "folder", "config": {"path": "/docs"}, "name": ""},
            422,
            "validation_error",
            "name",
        ),
    ],
)
def test_invalid_sources_are_rejected_with_the_field(
    client: TestClient, body: dict[str, Any], status: int, code: str, field: str
) -> None:
    response = client.post("/api/sources", json=body)

    assert response.status_code == status
    error = response.json()
    assert error["code"] == code
    assert error["errors"][0]["field"] == field
    assert client.get("/api/sources").json()["total"] == 0


def test_adding_the_same_folder_twice_is_a_conflict(
    client: TestClient, tmp_path: Path
) -> None:
    _add_folder(client, tmp_path / "docs")

    response = client.post(
        "/api/sources",
        json={"kind": "folder", "config": {"path": str(tmp_path / "docs")}},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "duplicate_source"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/sources/404"),
        ("PATCH", "/api/sources/404"),
        ("DELETE", "/api/sources/404"),
        ("POST", "/api/sources/404/pause"),
        ("POST", "/api/sources/404/resume"),
        ("POST", "/api/sources/404/sync"),
        ("GET", "/api/sources/404/exclusions"),
        ("DELETE", "/api/sources/404/exclusions/1"),
    ],
)
def test_unknown_sources_are_not_found(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, path, json={"name": "x"})

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def _wait_for_titles(client: TestClient, titles: list[str]) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        items = client.get("/api/docs").json()["items"]
        if sorted(document["title"] for document in items) == titles:
            return
        time.sleep(0.05)
    raise AssertionError(f"the library never held {titles}")


def _excluded_guide(client: TestClient, folder: Path) -> tuple[int, dict[str, Any]]:
    folder.mkdir()
    (folder / "guide.md").write_text("# Guide\n\nInstall it.")
    source = _add_folder(client, folder, rules=MANUAL_AUDIO)
    _wait_for_titles(client, ["Guide"])
    [document] = client.get("/api/docs").json()["items"]
    assert client.delete(f"/api/docs/{document['id']}").status_code == 204
    page = client.get(f"/api/sources/{source['id']}/exclusions").json()
    [exclusion] = page["items"]
    return source["id"], exclusion


def test_excluded_files_are_listed_and_can_be_reimported(
    client: TestClient, tmp_path: Path
) -> None:
    source_id, exclusion = _excluded_guide(client, tmp_path / "docs")

    response = client.delete(f"/api/sources/{source_id}/exclusions/{exclusion['id']}")

    assert (exclusion["name"], exclusion["item_key"]) == ("guide.md", "guide.md")
    assert response.status_code == 204
    _wait_for_titles(client, ["Guide"])
    page = client.get(f"/api/sources/{source_id}/exclusions").json()
    assert page["total"] == 0
    activity = client.get("/api/sources/activity").json()["items"]
    assert "reimport" in {entry["action"] for entry in activity}


def test_another_sources_exclusion_is_not_found(
    client: TestClient, tmp_path: Path
) -> None:
    _, exclusion = _excluded_guide(client, tmp_path / "docs")
    other = _add_folder(client, tmp_path / "other")

    response = client.delete(f"/api/sources/{other['id']}/exclusions/{exclusion['id']}")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


@pytest.mark.parametrize(
    "path",
    [
        "/api/sources/0/exclusions",
        f"/api/sources/{2**63}/exclusions",
        "/api/sources/1/exclusions/0",
        f"/api/sources/1/exclusions/{2**63}",
    ],
)
def test_out_of_range_exclusion_ids_are_rejected(client: TestClient, path: str) -> None:
    method = "GET" if path.endswith("exclusions") else "DELETE"

    response = client.request(method, path)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


@pytest.fixture
def env_folder_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setenv("PHEMIUS_WATCH_DIR", str(tmp_path / "listen"))
    with TestClient(create_app(), base_url=LOCAL_URL) as test_client:
        yield test_client


def test_the_environment_folder_is_locked(env_folder_client: TestClient) -> None:
    [source] = env_folder_client.get("/api/sources").json()["items"]

    response = env_folder_client.delete(f"/api/sources/{source['id']}")

    assert source["is_locked"] is True
    assert response.status_code == 409
    assert response.json()["code"] == "setting_locked"


def test_sources_need_the_token_in_network_mode(network_client: TestClient) -> None:
    assert network_client.get("/api/sources").status_code == 401
    assert network_client.get("/api/sources/activity").status_code == 401
    response = network_client.post(
        "/api/sources", json={"kind": "folder", "config": {"path": "/docs"}}
    )
    assert response.status_code == 401


def test_a_cross_site_request_cannot_add_a_source(
    client: TestClient, tmp_path: Path
) -> None:
    response = client.post(
        "/api/sources",
        json={"kind": "folder", "config": {"path": str(tmp_path)}},
        headers={"Sec-Fetch-Site": "cross-site"},
    )

    assert response.status_code == 403
    assert client.get("/api/sources").json()["total"] == 0
