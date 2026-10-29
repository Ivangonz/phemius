import pytest
from fastapi.testclient import TestClient

HOSTILE_IDS = ["abc", "0", "-1", "1.5", str(2**63), "9" * 40]

ID_ROUTES = [
    ("GET", "/api/docs/{id}"),
    ("DELETE", "/api/docs/{id}"),
    ("GET", "/api/docs/{id}/versions"),
    ("POST", "/api/docs/{id}/audio"),
    ("GET", "/api/audio/{id}"),
    ("GET", "/api/audio/{id}/url"),
    ("GET", "/api/audio/{id}/file"),
    ("GET", "/api/sources/{id}"),
    ("PATCH", "/api/sources/{id}"),
    ("DELETE", "/api/sources/{id}"),
    ("POST", "/api/sources/{id}/pause"),
    ("POST", "/api/sources/{id}/resume"),
    ("POST", "/api/sources/{id}/sync"),
    ("POST", "/api/queue/{id}/cancel"),
    ("POST", "/api/queue/{id}/retry"),
    ("GET", "/api/sources/activity?source_id={id}"),
]

LIST_ROUTES = [
    "/api/docs",
    "/api/docs/1/versions",
    "/api/queue",
    "/api/sources",
    "/api/sources/activity",
]


@pytest.mark.parametrize(("method", "route"), ID_ROUTES)
@pytest.mark.parametrize("hostile_id", HOSTILE_IDS)
def test_malformed_ids_are_rejected_on_every_route(
    client: TestClient, method: str, route: str, hostile_id: str
) -> None:
    response = client.request(method, route.format(id=hostile_id), json={})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


@pytest.mark.parametrize("route", LIST_ROUTES)
@pytest.mark.parametrize("hostile_offset", ["-1", str(2**63), "9" * 40])
def test_out_of_range_offsets_are_rejected(
    client: TestClient, route: str, hostile_offset: str
) -> None:
    response = client.get(route, params={"offset": hostile_offset})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_the_largest_id_is_not_found_rather_than_rejected(client: TestClient) -> None:
    assert client.get(f"/api/audio/{2**63 - 1}").status_code == 404
