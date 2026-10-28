from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from phemius import config
from phemius.app import create_app

ENV_NAMES = ["DATA_DIR", "MODEL", "TTS", "VOICE", "WATCH_DIR", "FORMAT", "LOG_LEVEL"]


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A fresh data folder, the stub voice and no model key for every test."""
    for name in ENV_NAMES:
        monkeypatch.delenv(config.ENV_PREFIX + name, raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    data_dir = tmp_path / "data"
    monkeypatch.setenv("PHEMIUS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("PHEMIUS_TTS", "stub")
    yield data_dir


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client
