import json
from typing import Any

import httpx2
import pytest
from openai import DefaultHttpxClient

from phemius.config import load_config
from phemius.errors import ModelError
from phemius.models.openrouter import OpenRouterModel, from_config


def _completion(content: str, finish_reason: str = "stop") -> dict[str, Any]:
    return {
        "id": "gen-1",
        "object": "chat.completion",
        "created": 0,
        "model": "test/model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
    }


def _model(status: int, body: dict[str, Any]) -> OpenRouterModel:
    transport = httpx2.MockTransport(
        lambda request: httpx2.Response(status, content=json.dumps(body))
    )
    return OpenRouterModel(
        "sk-or-secret",
        "test/model",
        script_max_tokens=100,
        http_client=DefaultHttpxClient(transport=transport),
    )


def test_write_script_returns_message_content() -> None:
    model = _model(200, _completion("  A spoken script.\n"))

    assert model.write_script("Setup", "# Setup", "neutral") == "A spoken script."


def test_length_finish_reason_raises_instead_of_truncating() -> None:
    model = _model(200, _completion("Cut off mid", finish_reason="length"))

    with pytest.raises(ModelError, match="100-token limit") as raised:
        model.write_script("Setup", "# Setup", "neutral")

    assert raised.value.hint is not None and "OpenRouter credit" in raised.value.hint


def test_402_maps_to_credit_hint_without_provider_text() -> None:
    body = {"error": {"message": "Insufficient credits for key sk-or-secret"}}
    model = _model(402, body)

    with pytest.raises(ModelError) as raised:
        model.write_script("Setup", "# Setup", "neutral")

    assert raised.value.message == "OpenRouter returned 402."
    assert raised.value.hint is not None and "credits" in raised.value.hint
    assert "sk-or-secret" not in str(raised.value)


def test_401_points_at_the_api_key() -> None:
    model = _model(401, {"error": {"message": "No auth credentials found"}})

    with pytest.raises(ModelError) as raised:
        model.write_script("Setup", "# Setup", "neutral")

    assert raised.value.hint == "Check OPENROUTER_API_KEY."


def test_analyze_parses_the_json_reply() -> None:
    reply = 'Sure: {"category": "reference / API", "summary": "Lists endpoints."}'
    model = _model(200, _completion(reply))

    analysis = model.analyze("API", "GET /docs returns documents.")

    assert analysis == {
        "category": "reference / API",
        "summary": "Lists endpoints.",
        "suggested_tone": "neutral",
    }


def test_check_reports_model_and_latency() -> None:
    model = _model(200, _completion("OK", finish_reason="length"))

    result = model.check()

    assert result.is_reachable
    assert result.model == "test/model"
    assert result.latency_ms is not None and result.latency_ms > 0


def test_check_reports_failure_with_hint() -> None:
    model = _model(402, {"error": {"message": "Insufficient credits"}})

    result = model.check()

    assert not result.is_reachable
    assert result.error == "OpenRouter returned 402."
    assert result.hint is not None and "credits" in result.hint


def test_from_config_without_key_raises_with_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", "openrouter")

    with pytest.raises(ModelError) as raised:
        from_config(load_config())

    assert raised.value.hint is not None and "OPENROUTER_API_KEY" in raised.value.hint
