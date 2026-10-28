import sys

import pytest
from fastapi.testclient import TestClient

from phemius.app import create_app
from phemius.services.library_config import LibraryConfig
from phemius.voices.kokoro import INSTALL_HINT
from tests.conftest import LOCAL_URL
from tests.services.fakes import FakeFfmpeg, UseFfmpeg


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

    with TestClient(create_app(), base_url=LOCAL_URL) as client:
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


@pytest.mark.parametrize(
    ("provider", "env", "expected_model"),
    [
        ("offline", {}, "offline rules"),
        ("openrouter", {"OPENROUTER_API_KEY": "sk-or-secret"}, "vendor/chat-model"),
        ("openai", {"OPENAI_API_KEY": "sk-secret"}, "vendor/chat-model"),
        (
            "openai_compatible",
            {"PHEMIUS_SCRIPT_BASE_URL": "http://localhost:1234/v1"},
            "vendor/chat-model",
        ),
        ("ollama", {"PHEMIUS_OLLAMA_MODEL": "qwen2.5:7b"}, "qwen2.5:7b"),
    ],
)
def test_config_reports_the_model_of_the_configured_provider(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    env: dict[str, str],
    expected_model: str,
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", provider)
    monkeypatch.setenv("PHEMIUS_MODEL", "vendor/chat-model")
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    body = client.get("/api/config").json()

    assert body["script_provider"] == provider
    assert body["model"] == expected_model
    assert body["llm_hint"] is None
    assert LibraryConfig.model_validate(body).model_dump() == body


def test_config_answers_with_a_hint_when_the_provider_key_is_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", "openai")
    monkeypatch.setenv("PHEMIUS_MODEL", "gpt-4o-mini")

    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["model"] == "gpt-4o-mini"
    assert response.json()["llm_error"] == "OpenAI needs an API key."
    assert "OPENAI_API_KEY" in response.json()["llm_hint"]
    LibraryConfig.model_validate(response.json())


def test_config_reports_ffmpeg_version(
    client: TestClient, use_ffmpeg: UseFfmpeg
) -> None:
    use_ffmpeg(FakeFfmpeg(stdout=b"ffmpeg version 7.1 Copyright\n"))

    body = client.get("/api/config").json()

    assert body["ffmpeg"] == {
        "is_present": True,
        "version": "7.1",
        "status": "ok",
        "message": "ffmpeg 7.1 converts audio to M4A or MP3.",
        "hint": None,
    }


def test_config_reports_missing_ffmpeg_as_optional(
    client: TestClient, use_ffmpeg: UseFfmpeg
) -> None:
    use_ffmpeg(None)

    ffmpeg_check = client.get("/api/config").json()["ffmpeg"]

    assert (ffmpeg_check["is_present"], ffmpeg_check["status"]) == (False, "optional")
    assert ffmpeg_check["hint"]


def test_config_schema_names_every_field_of_the_response(client: TestClient) -> None:
    body = client.get("/api/config").json()
    schema = client.get("/openapi.json").json()

    response_schema = schema["paths"]["/api/config"]["get"]["responses"]["200"]
    assert response_schema["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/LibraryConfig"
    }
    assert set(schema["components"]["schemas"]["LibraryConfig"]["properties"]) == set(
        body
    )
