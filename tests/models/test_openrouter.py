import json
from typing import Any

import httpx2
import pytest
from openai import DefaultHttpxClient

from phemius.errors import ModelError
from phemius.models.openrouter import OpenRouterClient


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


def _client(status: int, body: dict[str, Any]) -> OpenRouterClient:
    transport = httpx2.MockTransport(
        lambda request: httpx2.Response(status, content=json.dumps(body))
    )
    return OpenRouterClient(
        "sk-or-secret",
        "test/model",
        http_client=DefaultHttpxClient(transport=transport),
    )


def test_complete_returns_message_content() -> None:
    client = _client(200, _completion("A spoken script."))

    assert client.complete("system", "user", max_tokens=100) == "A spoken script."


def test_length_finish_reason_raises_instead_of_truncating() -> None:
    client = _client(200, _completion("Cut off mid", finish_reason="length"))

    with pytest.raises(ModelError, match="100-token limit") as raised:
        client.complete("system", "user", max_tokens=100)

    assert raised.value.hint


def test_402_maps_to_credit_hint_without_provider_text() -> None:
    body = {"error": {"message": "Insufficient credits for key sk-or-secret"}}
    client = _client(402, body)

    with pytest.raises(ModelError) as raised:
        client.complete("system", "user", max_tokens=100)

    assert raised.value.message == "OpenRouter returned 402."
    assert raised.value.hint is not None and "credits" in raised.value.hint
    assert "sk-or-secret" not in str(raised.value)


def test_401_points_at_the_api_key() -> None:
    client = _client(401, {"error": {"message": "No auth credentials found"}})

    with pytest.raises(ModelError) as raised:
        client.complete("system", "user", max_tokens=100)

    assert raised.value.hint == "Check OPENROUTER_API_KEY."
