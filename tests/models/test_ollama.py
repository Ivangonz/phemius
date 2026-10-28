import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from phemius.config import load_config
from phemius.errors import ModelError
from phemius.models import get_script_model
from phemius.models.ollama import InstalledModel, OllamaModel

type Handler = Callable[[httpx2.Request], httpx2.Response]

TAGS = {
    "models": [
        {"name": "qwen2.5:7b", "size": 4_683_087_332},
        {"name": "llama3.2:latest", "size": 2_019_393_189},
    ]
}


def _chat_reply(content: str, done_reason: str = "stop") -> dict[str, Any]:
    return {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": content},
        "done": True,
        "done_reason": done_reason,
    }


def _respond(status: int, body: dict[str, Any]) -> Handler:
    return lambda request: httpx2.Response(status, content=json.dumps(body))


def _refuse_connection(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("Connection refused", request=request)


def _model(handler: Handler, model: str = "llama3.2") -> OllamaModel:
    client = httpx2.Client(
        base_url="http://ollama.test", transport=httpx2.MockTransport(handler)
    )
    return OllamaModel(model, script_max_tokens=100, http_client=client)


def test_list_models_returns_names_and_sizes_sorted_by_name() -> None:
    model = _model(_respond(200, TAGS))

    assert model.list_models() == [
        InstalledModel(name="llama3.2:latest", size_bytes=2_019_393_189),
        InstalledModel(name="qwen2.5:7b", size_bytes=4_683_087_332),
    ]


def test_check_is_ready_when_the_model_is_pulled() -> None:
    result = _model(_respond(200, TAGS)).check()

    assert result.is_reachable
    assert result.model == "llama3.2"
    assert result.error is None


def test_check_gives_the_pull_hint_for_an_unknown_model() -> None:
    result = _model(_respond(200, TAGS), model="mistral").check()

    assert not result.is_reachable
    assert result.error == "Ollama model 'mistral' is not pulled."
    assert result.hint == "Run `ollama pull mistral`."


def test_check_reports_ollama_not_running() -> None:
    result = _model(_refuse_connection).check()

    assert not result.is_reachable
    assert result.error is not None and "not running" in result.error
    assert result.hint is not None and "ollama serve" in result.hint


def test_write_script_sends_a_non_streaming_chat_and_cleans_the_reply() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        reply = _chat_reply("Here is the script:\n\n```\nThis covers setup.\n```")
        return httpx2.Response(200, content=json.dumps(reply))

    script = _model(handler).write_script("Setup", "# Setup", "neutral")

    assert script == "This covers setup."
    assert requests[0]["model"] == "llama3.2"
    assert requests[0]["stream"] is False
    assert requests[0]["options"]["num_predict"] == 100


def test_context_window_fits_the_prompt_and_the_reply() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        return httpx2.Response(200, content=json.dumps(_chat_reply("A script.")))

    _model(handler).write_script("Long", "word " * 6000, "neutral")

    assert requests[0]["options"]["num_ctx"] > 30_000 // 4 + 100


def test_length_done_reason_raises_instead_of_truncating() -> None:
    model = _model(_respond(200, _chat_reply("Cut off", done_reason="length")))

    with pytest.raises(ModelError, match="100-token limit"):
        model.write_script("Setup", "# Setup", "neutral")


def test_chat_with_a_missing_model_gives_the_pull_hint() -> None:
    body = {"error": "model 'mistral' not found, try pulling it first"}
    model = _model(_respond(404, body), model="mistral")

    with pytest.raises(ModelError) as raised:
        model.write_script("Setup", "# Setup", "neutral")

    assert raised.value.hint == "Run `ollama pull mistral`."


def test_chat_timeout_points_at_the_timeout_setting() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("timed out", request=request)

    with pytest.raises(ModelError) as raised:
        _model(handler).write_script("Setup", "# Setup", "neutral")

    assert raised.value.hint is not None
    assert "PHEMIUS_OLLAMA_TIMEOUT" in raised.value.hint


def test_analyze_parses_the_json_reply() -> None:
    reply = '{"category": "reference / API", "summary": "Lists endpoints."}'
    model = _model(_respond(200, _chat_reply(reply)))

    assert model.analyze("API", "GET /docs")["category"] == "reference / API"


def test_provider_setting_selects_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", "ollama")
    monkeypatch.setenv("PHEMIUS_OLLAMA_MODEL", "qwen2.5:7b")

    model = get_script_model(load_config())

    assert isinstance(model, OllamaModel)
    assert model.model == "qwen2.5:7b"
