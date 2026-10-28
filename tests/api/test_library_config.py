import sys

import pytest
from fastapi.testclient import TestClient

from phemius.app import create_app
from phemius.voices.kokoro import INSTALL_HINT


def test_config_lists_namespaced_voices_of_configured_engine(
    client: TestClient,
) -> None:
    body = client.get("/api/config").json()

    assert body["voices"] == {"stub:silent": "Silent (test engine)"}
    assert body["default_voice"] == "stub:silent"
    assert body["tts_status"]["is_ready"] is True


def test_missing_kokoro_reports_install_hint_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_TTS", "kokoro")
    monkeypatch.setitem(sys.modules, "kokoro", None)

    with TestClient(create_app()) as client:
        body = client.get("/api/config").json()

    assert body["default_voice"] == "kokoro:af_heart"
    assert body["tts_status"] == {
        "is_ready": False,
        "message": "Kokoro is not installed.",
        "hint": INSTALL_HINT,
    }


def test_config_reports_offline_rules_without_a_model(client: TestClient) -> None:
    body = client.get("/api/config").json()

    assert body["llm"] is False
    assert body["script_provider"] == "offline"


def test_config_reports_configured_provider_without_the_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-secret")

    response = client.get("/api/config")

    assert response.json()["llm"] is True
    assert response.json()["script_provider"] == "openrouter"
    assert "sk-or-secret" not in response.text
