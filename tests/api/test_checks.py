import pytest
from fastapi.testclient import TestClient

from phemius.services import checks
from tests.services.fakes import FakeFfmpeg, UseFfmpeg


@pytest.fixture(autouse=True)
def no_previous_run(use_ffmpeg: UseFfmpeg, monkeypatch: pytest.MonkeyPatch) -> None:
    use_ffmpeg(FakeFfmpeg(stdout=b"ffmpeg version 7.1.1\n"))
    monkeypatch.setattr(checks, "_last_run", None)


def test_last_run_is_null_before_checks_run(client: TestClient) -> None:
    response = client.get("/api/checks")

    assert response.status_code == 200
    assert response.json() is None


def test_running_checks_returns_each_check_and_a_summary(client: TestClient) -> None:
    response = client.post("/api/checks")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"checks", "summary", "ran_at"}
    assert set(body["checks"][0]) == {"id", "label", "detail", "status", "hint"}
    assert sum(body["summary"].values()) == len(body["checks"])


def test_last_run_returns_the_previous_result(client: TestClient) -> None:
    ran = client.post("/api/checks").json()

    response = client.get("/api/checks")

    assert response.json() == ran
