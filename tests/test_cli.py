from pathlib import Path
from typing import Any

import pytest

from phemius import cli
from phemius.store import settings as settings_store
from phemius.store.database import init_database


@pytest.fixture
def uvicorn_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("uvicorn.run", lambda app, **options: calls.append(options))
    return calls


def test_serve_binds_to_localhost_by_default(
    uvicorn_calls: list[dict[str, Any]],
) -> None:
    cli.main(["serve"])

    assert uvicorn_calls[0]["host"] == "127.0.0.1"
    assert uvicorn_calls[0]["port"] == 8000
    assert uvicorn_calls[0]["proxy_headers"] is False


def test_serve_binds_to_all_interfaces_in_network_mode(
    uvicorn_calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_ACCESS_MODE", "network")

    cli.main(["serve", "--port", "9000"])

    assert uvicorn_calls[0]["host"] == "0.0.0.0"
    assert uvicorn_calls[0]["port"] == 9000


def test_serve_uses_the_saved_access_mode(
    uvicorn_calls: list[dict[str, Any]], isolated_env: Path
) -> None:
    init_database(isolated_env / "library.db")
    settings_store.save_settings({"access_mode": "proxy"})

    cli.main(["serve"])

    assert uvicorn_calls[0]["host"] == "127.0.0.1"
    assert uvicorn_calls[0]["proxy_headers"] is True


def test_serve_disables_the_access_log_so_query_tokens_are_not_logged(
    uvicorn_calls: list[dict[str, Any]],
) -> None:
    cli.main(["serve"])

    assert uvicorn_calls[0]["access_log"] is False
