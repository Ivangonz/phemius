import json
import logging
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from openai import DefaultHttpxClient
from structlog.testing import capture_logs

from phemius.config import load_config
from phemius.errors import ModelError
from phemius.models import get_script_model, openai_compatible
from phemius.models.base import TokenUsage
from phemius.models.openai_compatible import OpenAICompatibleModel

BASE_URL = "http://localhost:1234/v1"
SECRET = "sk-test-secret-key"

type Handler = Callable[[httpx2.Request], httpx2.Response]


def _completion(content: str, finish_reason: str = "stop") -> dict[str, Any]:
    return {
        "id": "gen-1",
        "object": "chat.completion",
        "created": 0,
        "model": "local/model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
    }


def _reply(status: int, body: dict[str, Any]) -> Handler:
    return lambda request: httpx2.Response(status, content=json.dumps(body))


def _raise(error: Exception) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise error

    return handler


def _model(handler: Handler, api_key: str | None = SECRET) -> OpenAICompatibleModel:
    return OpenAICompatibleModel(
        BASE_URL,
        api_key,
        "local/model",
        script_max_tokens=100,
        http_client=DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
        max_retries=0,
    )


def test_write_script_posts_to_the_base_url_with_the_key() -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return _reply(200, _completion("  A spoken script.\n"))(request)

    script = _model(handler).write_script("Setup", "# Setup", "neutral")

    assert script.text == "A spoken script."
    assert str(requests[0].url) == f"{BASE_URL}/chat/completions"
    assert requests[0].headers["Authorization"] == f"Bearer {SECRET}"


def test_server_without_a_key_never_receives_openai_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-key")
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return _reply(200, _completion("Script."))(request)

    _model(handler, api_key=None).write_script("Setup", "# Setup", "neutral")

    assert "sk-openai-key" not in str(requests[0].headers)


def test_length_finish_reason_raises_instead_of_truncating() -> None:
    model = _model(_reply(200, _completion("Cut off mid", finish_reason="length")))

    with pytest.raises(ModelError, match="100-token limit") as raised:
        model.write_script("Setup", "# Setup", "neutral")

    assert raised.value.hint is not None
    assert "PHEMIUS_SCRIPT_MAX_TOKENS" in raised.value.hint


@pytest.mark.parametrize(
    ("status", "hint_part"),
    [
        (401, "Check PHEMIUS_SCRIPT_API_KEY."),
        (402, "credits"),
        (404, "PHEMIUS_MODEL"),
        (429, "rate limiting"),
    ],
)
def test_error_status_maps_to_model_error_with_hint(
    status: int, hint_part: str
) -> None:
    body = {"error": {"message": f"Rejected key {SECRET}"}}
    model = _model(_reply(status, body))

    with pytest.raises(ModelError) as raised:
        model.write_script("Setup", "# Setup", "neutral")

    assert raised.value.message == f"localhost:1234 returned {status}."
    assert raised.value.hint is not None and hint_part in raised.value.hint
    assert SECRET not in str(raised.value)


def test_refused_connection_points_at_the_base_url() -> None:
    model = _model(_raise(httpx2.ConnectError("Connection refused")))

    with pytest.raises(ModelError) as raised:
        model.write_script("Setup", "# Setup", "neutral")

    assert raised.value.message == "Could not reach localhost:1234."
    assert raised.value.hint is not None
    assert "PHEMIUS_SCRIPT_BASE_URL" in raised.value.hint


def test_timeout_raises_model_error() -> None:
    model = _model(_raise(httpx2.ReadTimeout("timed out")))

    with pytest.raises(ModelError) as raised:
        model.write_script("Setup", "# Setup", "neutral")

    assert raised.value.message == "localhost:1234 did not answer in time."
    assert raised.value.hint is not None


def test_analyze_parses_the_json_reply() -> None:
    reply = 'Sure: {"category": "reference / API", "summary": "Lists endpoints."}'
    model = _model(_reply(200, _completion(reply)))

    analysis = model.analyze("API", "GET /docs returns documents.")

    assert analysis["category"] == "reference / API"
    assert analysis["summary"] == "Lists endpoints."
    assert analysis["suggested_tone"] == "neutral"


def test_check_reports_model_and_latency() -> None:
    model = _model(_reply(200, _completion("OK", finish_reason="length")))

    result = model.check()

    assert result.is_reachable
    assert result.model == "local/model"
    assert result.latency_ms is not None and result.latency_ms > 0


def test_check_reports_failure_with_hint() -> None:
    model = _model(_raise(httpx2.ConnectError("Connection refused")))

    result = model.check()

    assert not result.is_reachable
    assert result.error == "Could not reach localhost:1234."
    assert result.hint is not None


def test_api_key_never_appears_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    with capture_logs() as logs:
        _model(_reply(200, _completion("Script."))).write_script("A", "B", "neutral")
        _model(_reply(401, {"error": {"message": SECRET}})).check()

    assert logs
    assert SECRET not in repr(logs)
    assert SECRET not in caplog.text


def test_script_carries_the_token_counts_the_server_reported() -> None:
    usage = {"prompt_tokens": 1200, "completion_tokens": 300, "total_tokens": 1500}
    body = {**_completion("Script."), "usage": usage}

    script = _model(_reply(200, body)).write_script("A", "B", "neutral")

    assert script.usage == TokenUsage(input_tokens=1200, output_tokens=300)


def test_script_carries_the_cost_a_provider_such_as_openrouter_reports() -> None:
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    body = {**_completion("Script."), "usage": {**usage, "cost": 0.0042}}

    script = _model(_reply(200, body)).write_script("A", "B", "neutral")

    assert script.usage.provider_cost_usd == 0.0042
    assert not script.usage.is_local


def test_script_without_reported_usage_has_unknown_tokens() -> None:
    script = _model(_reply(200, _completion("Script."))).write_script("A", "B", "x")

    assert script.usage == TokenUsage()


def test_custom_server_needs_a_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", "openai_compatible")

    with pytest.raises(ModelError) as raised:
        openai_compatible.from_config(load_config())

    assert raised.value.hint is not None
    assert "PHEMIUS_SCRIPT_BASE_URL" in raised.value.hint


def test_custom_server_uses_base_url_without_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", "openai_compatible")
    monkeypatch.setenv("PHEMIUS_SCRIPT_BASE_URL", BASE_URL)

    model = openai_compatible.from_config(load_config())

    assert model.base_url == BASE_URL


@pytest.mark.parametrize(
    ("provider", "key_env", "base_url"),
    [
        ("openai", "OPENAI_API_KEY", openai_compatible.OPENAI_BASE_URL),
        ("openrouter", "OPENROUTER_API_KEY", openai_compatible.OPENROUTER_BASE_URL),
    ],
)
def test_preset_fills_in_the_base_url(
    monkeypatch: pytest.MonkeyPatch, provider: str, key_env: str, base_url: str
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", provider)
    monkeypatch.setenv(key_env, SECRET)

    model = get_script_model(load_config())

    assert isinstance(model, OpenAICompatibleModel)

    assert model.base_url == base_url


@pytest.mark.parametrize(
    ("provider", "key_env"),
    [("openai", "OPENAI_API_KEY"), ("openrouter", "OPENROUTER_API_KEY")],
)
def test_preset_without_a_key_raises_with_hint(
    monkeypatch: pytest.MonkeyPatch, provider: str, key_env: str
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", provider)

    with pytest.raises(ModelError) as raised:
        get_script_model(load_config())

    assert raised.value.hint is not None and key_env in raised.value.hint


def test_preset_errors_name_the_provider_and_its_key() -> None:
    model = OpenAICompatibleModel(
        openai_compatible.OPENROUTER_BASE_URL,
        SECRET,
        "test/model",
        script_max_tokens=100,
        http_client=DefaultHttpxClient(
            transport=httpx2.MockTransport(_reply(401, {"error": {}}))
        ),
        max_retries=0,
        provider=openai_compatible.OPENROUTER,
    )

    with pytest.raises(ModelError) as raised:
        model.write_script("Setup", "# Setup", "neutral")

    assert raised.value.message == "OpenRouter returned 401."
    assert raised.value.hint == "Check OPENROUTER_API_KEY."
