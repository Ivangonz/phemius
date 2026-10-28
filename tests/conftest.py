from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from phemius import config
from phemius.app import create_app
from phemius.models import SCRIPT_MODELS
from phemius.models.base import ScriptModel
from phemius.services import ffmpeg
from phemius.store import database
from tests.services.fakes import FAKE_EXECUTABLE, FakeFfmpeg, UseFfmpeg

LOCAL_URL = "http://127.0.0.1:8000"

ENV_NAMES = [
    "DATA_DIR",
    "MODEL",
    "SCRIPT_PROVIDER",
    "TTS",
    "VOICE",
    "WATCH_DIR",
    "WATCH_ON_CHANGE",
    "SKIP_NOT_RECOMMENDED",
    "FORMAT",
    "SCRIPT_MAX_TOKENS",
    "SCRIPT_WORKERS",
    "LOG_LEVEL",
    "SCRIPT_BASE_URL",
    "SCRIPT_API_KEY",
    "OLLAMA_URL",
    "OLLAMA_MODEL",
    "OLLAMA_TIMEOUT",
    "OPENAI_SPEECH_BASE_URL",
    "OPENAI_SPEECH_API_KEY",
    "OPENAI_SPEECH_MODEL",
    "OPENAI_SPEECH_VOICES",
    "ELEVENLABS_VOICES",
    "ACCESS_MODE",
    "ACCESS_TOKEN",
]


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A fresh data folder, the stub voice and no model key for every test."""
    for name in ENV_NAMES:
        monkeypatch.delenv(config.ENV_PREFIX + name, raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    # Without this, saved settings from an earlier test's library would leak in.
    monkeypatch.setattr(database, "_db_path", None)
    data_dir = tmp_path / "data"
    monkeypatch.setenv("PHEMIUS_DATA_DIR", str(data_dir))
    monkeypatch.setenv("PHEMIUS_TTS", "stub")
    yield data_dir


@pytest.fixture
def client() -> Iterator[TestClient]:
    # Local mode accepts only loopback Host headers, unlike the default testserver.
    with TestClient(create_app(), base_url=LOCAL_URL) as test_client:
        yield test_client


@pytest.fixture
def use_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> UseFfmpeg:
    """Replaces the ffmpeg binary with `fake`, or removes it when `fake` is None."""

    def use(fake: FakeFfmpeg | None) -> FakeFfmpeg:
        executable = None if fake is None else FAKE_EXECUTABLE
        monkeypatch.setattr(ffmpeg, "find_ffmpeg", lambda: executable)
        fake = fake or FakeFfmpeg()
        monkeypatch.setattr(ffmpeg, "run_ffmpeg", fake.run)
        return fake

    return use


@pytest.fixture
def use_script_model(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[ScriptModel], None]:
    """Registers `model` as a provider and selects it, as a real adapter would be."""

    def use(model: ScriptModel) -> None:
        monkeypatch.setitem(SCRIPT_MODELS, "fake", lambda loaded_config: model)
        monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", "fake")

    return use
