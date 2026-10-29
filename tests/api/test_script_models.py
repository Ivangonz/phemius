import json
from collections.abc import Callable, Iterator

import httpx2
import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from phemius.app import create_app
from phemius.config import Config
from phemius.models import SCRIPT_MODELS, ollama
from phemius.models.base import ScriptModelCheck
from phemius.models.ollama import OllamaModel
from phemius.services import access
from tests.api.test_access import _bearer
from tests.models.fakes import FakeScriptModel, UseScriptModel
from tests.models.test_ollama import TAGS, Handler, _refuse_connection, _respond

SECRET = "sk-or-very-secret"

type UseOllama = Callable[[Handler], None]


@pytest.fixture
def use_ollama(monkeypatch: pytest.MonkeyPatch) -> UseOllama:
    """Answers Ollama requests with `handler` instead of the network."""

    def use(handler: Handler) -> None:
        def from_config(config: Config) -> OllamaModel:
            client = httpx2.Client(
                base_url=config.ollama_url, transport=httpx2.MockTransport(handler)
            )
            return OllamaModel(config.ollama_model, 100, client)

        monkeypatch.setattr(ollama, "from_config", from_config)
        monkeypatch.setitem(SCRIPT_MODELS, "ollama", from_config)

    return use


class UnreachableScriptModel(FakeScriptModel):
    def check(self) -> ScriptModelCheck:
        return ScriptModelCheck(
            is_reachable=False,
            model=self.model,
            error="Provider returned 401.",
            hint="Check the API key.",
        )


def test_lists_installed_ollama_models(
    client: TestClient, use_ollama: UseOllama
) -> None:
    use_ollama(_respond(200, TAGS))

    response = client.get("/api/models/ollama")

    assert response.status_code == 200
    assert response.json() == {
        "models": [
            {"name": "llama3.2:latest", "size_bytes": 2_019_393_189},
            {"name": "qwen2.5:7b", "size_bytes": 4_683_087_332},
        ]
    }


def test_ollama_not_running_is_a_model_error_with_a_hint(
    client: TestClient, use_ollama: UseOllama
) -> None:
    use_ollama(_refuse_connection)

    response = client.get("/api/models/ollama")

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "model_error"
    assert "not running" in body["detail"]
    assert "ollama serve" in body["hint"]


def test_ollama_models_use_the_saved_url(
    client: TestClient, use_ollama: UseOllama
) -> None:
    requested: list[str] = []

    def record(request: httpx2.Request) -> httpx2.Response:
        requested.append(str(request.url))
        return httpx2.Response(200, content=json.dumps(TAGS))

    use_ollama(record)
    client.patch("/api/settings", json={"ollama_url": "http://gpu-box:11434"})

    client.get("/api/models/ollama")

    assert requested == ["http://gpu-box:11434/api/tags"]


@pytest.fixture
def network_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("PHEMIUS_ACCESS_MODE", "network")
    with TestClient(create_app()) as test_client:
        yield test_client


def test_ollama_models_need_the_token_in_network_mode(
    network_client: TestClient, use_ollama: UseOllama
) -> None:
    use_ollama(_respond(200, TAGS))
    token = access.regenerate_token()

    assert network_client.get("/api/models/ollama").status_code == 401
    authorized = network_client.get("/api/models/ollama", headers=_bearer(token))
    assert authorized.status_code == 200


def test_check_reports_latency_for_a_reachable_model(
    client: TestClient, use_script_model: UseScriptModel
) -> None:
    use_script_model(FakeScriptModel())

    response = client.post("/api/models/check")

    assert response.status_code == 200
    assert response.json() == {
        "is_reachable": True,
        "provider": "fake",
        "model": "fake/model",
        "latency_ms": 1.0,
        "error": None,
        "hint": None,
    }


def test_check_reports_the_provider_error_and_hint(
    client: TestClient, use_script_model: UseScriptModel
) -> None:
    use_script_model(UnreachableScriptModel())

    body = client.post("/api/models/check").json()

    assert body["is_reachable"] is False
    assert body["error"] == "Provider returned 401."
    assert body["hint"] == "Check the API key."


def test_check_reports_a_missing_key_without_a_request(client: TestClient) -> None:
    client.patch("/api/settings", json={"script_provider": "openrouter"})

    body = client.post("/api/models/check").json()

    assert body["is_reachable"] is False
    assert body["provider"] == "openrouter"
    assert body["error"] == "OpenRouter needs an API key."
    assert body["hint"] is not None


def test_check_offline_rules_need_no_connection(client: TestClient) -> None:
    body = client.post("/api/models/check").json()

    assert body["is_reachable"] is True
    assert body["provider"] == "offline"
    assert body["latency_ms"] is None


def test_check_tests_the_saved_provider(
    client: TestClient, use_ollama: UseOllama
) -> None:
    use_ollama(_respond(200, TAGS))
    client.patch(
        "/api/settings",
        json={"script_provider": "ollama", "ollama_model": "qwen2.5:7b"},
    )

    body = client.post("/api/models/check").json()

    assert body["is_reachable"] is True
    assert body["provider"] == "ollama"
    assert body["model"] == "qwen2.5:7b"
    assert body["latency_ms"] is not None


def test_check_never_returns_or_logs_the_key(
    client: TestClient, use_script_model: UseScriptModel
) -> None:
    use_script_model(UnreachableScriptModel())
    client.patch("/api/settings", json={"openrouter_api_key": SECRET})

    with capture_logs() as logs:
        response = client.post("/api/models/check")

    assert SECRET not in response.text
    assert SECRET not in str(logs)
    assert any(entry["event"] == "script_model_checked" for entry in logs)
