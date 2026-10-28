import os
from pathlib import Path
from typing import Any

import pytest

from phemius import __version__, cli
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


def test_version_prints_the_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exited:
        cli.main(["--version"])

    assert exited.value.code == 0
    assert capsys.readouterr().out.strip() == f"phemius {__version__}"


def test_serve_uses_the_host_and_port_options(
    uvicorn_calls: list[dict[str, Any]],
) -> None:
    cli.main(["serve", "--host", "localhost", "--port", "8765"])

    assert uvicorn_calls[0]["host"] == "localhost"
    assert uvicorn_calls[0]["port"] == 8765


def test_data_dir_option_sets_the_data_folder_before_config_loads(
    uvicorn_calls: list[dict[str, Any]], tmp_path: Path
) -> None:
    data_dir = tmp_path / "elsewhere"

    cli.main(["serve", "--data-dir", str(data_dir)])

    assert os.environ["PHEMIUS_DATA_DIR"] == str(data_dir)
    assert (data_dir / "library.db").exists()


def test_serve_refuses_all_interfaces_in_local_mode(
    uvicorn_calls: list[dict[str, Any]], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exited:
        cli.main(["serve", "--host", "0.0.0.0"])

    assert exited.value.code == 1
    error_output = capsys.readouterr().err
    assert "0.0.0.0" in error_output
    assert "PHEMIUS_ACCESS_MODE=network" in error_output
    assert uvicorn_calls == []


def test_serve_allows_all_interfaces_when_a_token_is_required(
    uvicorn_calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_ACCESS_MODE", "network")
    monkeypatch.setenv("PHEMIUS_ACCESS_TOKEN", "a" * 32)

    cli.main(["serve", "--host", "0.0.0.0"])

    assert uvicorn_calls[0]["host"] == "0.0.0.0"


def test_serve_keeps_trusting_only_a_local_proxy_on_another_host(
    uvicorn_calls: list[dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_ACCESS_MODE", "proxy")

    cli.main(["serve", "--host", "0.0.0.0"])

    assert uvicorn_calls[0]["forwarded_allow_ips"] == "127.0.0.1"
