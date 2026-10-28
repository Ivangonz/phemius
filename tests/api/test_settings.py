import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from phemius.config import Config
from phemius.models import SCRIPT_MODELS
from tests.api.test_docs import _upload_sample, _wait_for_audio
from tests.models.fakes import FakeScriptModel

SECRET = "sk-or-very-secret"


def test_get_reports_value_source_and_lock(client: TestClient) -> None:
    body = client.get("/api/settings").json()

    assert body["values"]["voice_engine"] == {
        "value": "stub",
        "source": "env",
        "is_locked": True,
    }
    assert body["values"]["output_format"] == {
        "value": "wav",
        "source": "default",
        "is_locked": False,
    }
    assert body["values"]["script_provider"]["value"] == "offline"
    assert body["values"]["default_voice"]["value"] is None
    assert body["secrets"]["openrouter_api_key"] == {
        "has_key": False,
        "source": "default",
        "is_locked": False,
    }


def test_patch_saves_a_setting(client: TestClient) -> None:
    response = client.patch("/api/settings", json={"output_format": "mp3"})

    assert response.status_code == 200
    assert response.json()["values"]["output_format"] == {
        "value": "mp3",
        "source": "saved",
        "is_locked": False,
    }


@pytest.mark.parametrize(
    "key", ["openrouter_api_key", "openai_speech_api_key", "elevenlabs_api_key"]
)
def test_saved_key_is_never_returned_or_logged(client: TestClient, key: str) -> None:
    with capture_logs() as logs:
        patched = client.patch("/api/settings", json={key: SECRET})
        fetched = client.get("/api/settings")

    assert SECRET not in patched.text + fetched.text
    assert SECRET not in str(logs)
    assert fetched.json()["secrets"][key]["has_key"] is True
    assert any(
        entry["event"] == "settings_updated" and entry["keys"] == [key]
        for entry in logs
    )


def test_patch_null_clears_a_secret(client: TestClient) -> None:
    client.patch("/api/settings", json={"openrouter_api_key": SECRET})

    response = client.patch("/api/settings", json={"openrouter_api_key": None})

    assert response.json()["secrets"]["openrouter_api_key"]["has_key"] is False


def test_patch_rejects_a_value_locked_by_env(client: TestClient) -> None:
    response = client.patch(
        "/api/settings", json={"voice_engine": "kokoro", "model": "local/model"}
    )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "setting_locked"
    assert body["errors"] == [
        {"field": "voice_engine", "message": "Set by environment variable PHEMIUS_TTS"}
    ]
    assert client.get("/api/settings").json()["values"]["model"]["source"] == "default"


@pytest.mark.parametrize(
    ("field", "value"),
    [("output_format", "flac"), ("script_max_tokens", 0), ("unknown", "x")],
)
def test_patch_rejects_invalid_values_with_field_errors(
    client: TestClient, field: str, value: object
) -> None:
    response = client.patch("/api/settings", json={field: value})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == field


def test_next_job_uses_changed_provider_model_and_voice(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested_models: list[str] = []

    def fake_factory(config: Config) -> FakeScriptModel:
        requested_models.append(config.model)
        return FakeScriptModel(script="Saved settings script.")

    monkeypatch.setitem(SCRIPT_MODELS, "fake", fake_factory)
    monkeypatch.delenv("PHEMIUS_TTS")
    uploaded = _upload_sample(client, "deploy-guide.md")
    client.patch(
        "/api/settings",
        json={
            "script_provider": "fake",
            "model": "local/model",
            "voice_engine": "stub",
            "default_voice": "silent",
        },
    )

    created = client.post(f"/api/docs/{uploaded['doc_id']}/audio", json={})
    audio = _wait_for_audio(client, created.json()["audio_id"])

    assert audio["status"] == "done", audio["error"]
    assert audio["script"] == "Saved settings script."
    assert audio["voice"] == "stub:silent"
    assert requested_models[-1] == "local/model"
