"""A local Ollama server through its native API (`/api/chat`, `/api/tags`)."""

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx2

from phemius.config import Config
from phemius.errors import ModelError
from phemius.models.base import Script, ScriptModelCheck, SectionContext, TokenUsage
from phemius.models.chat import ChatReply, ChatScriptModel
from phemius.models.cleanup import clean_script

CHAT_PATH = "/api/chat"
CONNECT_TIMEOUT_SECONDS = 5.0
# A conservative estimate, so the context window is never too small for the prompt.
CHARS_PER_TOKEN = 3
MIN_CONTEXT_TOKENS = 8192


@dataclass(frozen=True)
class InstalledModel:
    name: str
    size_bytes: int


class OllamaModel(ChatScriptModel):
    def __init__(
        self, model: str, script_max_tokens: int, http_client: httpx2.Client
    ) -> None:
        super().__init__(model, script_max_tokens)
        self._client = http_client

    def write_script(
        self,
        title: str,
        text: str,
        tone: str,
        section: SectionContext | None = None,
    ) -> Script:
        script = super().write_script(title, text, tone, section)
        return Script(clean_script(script.text), script.usage)

    def list_models(self) -> list[InstalledModel]:
        """Models pulled into Ollama, sorted by name."""
        tags = self._request("GET", "/api/tags")
        try:
            installed = [
                InstalledModel(name=str(item["name"]), size_bytes=int(item["size"]))
                for item in tags["models"]
            ]
        except (KeyError, TypeError, ValueError) as error:
            raise ModelError("Ollama returned an unexpected model list.") from error
        return sorted(installed, key=lambda item: item.name)

    def check(self) -> ScriptModelCheck:
        started = time.perf_counter()
        try:
            installed = self.list_models()
            if not _is_installed(self.model, installed):
                raise _not_pulled(self.model)
        except ModelError as error:
            return ScriptModelCheck(
                is_reachable=False,
                model=self.model,
                error=error.message,
                hint=error.hint,
            )
        latency_ms = (time.perf_counter() - started) * 1000
        return ScriptModelCheck(
            is_reachable=True, model=self.model, latency_ms=latency_ms
        )

    def _chat(self, system: str, user: str, max_tokens: int) -> ChatReply:
        reply = self._request(
            "POST",
            CHAT_PATH,
            {
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "options": {
                    "num_predict": max_tokens,
                    "num_ctx": _context_tokens(system + user, max_tokens),
                },
            },
        )
        return _chat_reply(reply)

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, json=body)
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as error:
            raise ModelError(
                f"Ollama is not running at {self._client.base_url}.",
                hint="Start it with `ollama serve`, or set PHEMIUS_OLLAMA_URL.",
            ) from error
        except httpx2.TimeoutException as error:
            raise ModelError(
                "Ollama did not answer in time.",
                hint="Raise PHEMIUS_OLLAMA_TIMEOUT or pick a smaller model.",
            ) from error
        except httpx2.HTTPError as error:
            raise ModelError("Could not reach Ollama.") from error
        return self._parse(response, path)

    def _parse(self, response: httpx2.Response, path: str) -> dict[str, Any]:
        if response.status_code == 404 and path == CHAT_PATH:
            raise _not_pulled(self.model)
        if response.is_error:
            raise ModelError(
                f"Ollama returned {response.status_code}.",
                hint="Check PHEMIUS_OLLAMA_URL and the Ollama server log.",
            )
        try:
            data = response.json()
        except ValueError as error:
            raise ModelError("Ollama returned an unexpected reply.") from error
        if not isinstance(data, dict):
            raise ModelError("Ollama returned an unexpected reply.")
        return data


def from_config(config: Config) -> OllamaModel:
    return _cached_model(
        config.ollama_url,
        config.ollama_model,
        config.script_max_tokens,
        config.ollama_timeout,
    )


@lru_cache(maxsize=4)
def _cached_model(
    base_url: str, model: str, script_max_tokens: int, timeout_seconds: int
) -> OllamaModel:
    timeout = httpx2.Timeout(timeout_seconds, connect=CONNECT_TIMEOUT_SECONDS)
    client = httpx2.Client(base_url=base_url, timeout=timeout)
    return OllamaModel(model, script_max_tokens, client)


def _chat_reply(reply: dict[str, Any]) -> ChatReply:
    try:
        content = str(reply["message"]["content"])
    except (KeyError, TypeError) as error:
        raise ModelError("Ollama returned an unexpected reply.") from error
    return ChatReply(
        content=content,
        is_truncated=reply.get("done_reason") == "length",
        usage=TokenUsage(
            input_tokens=_count(reply.get("prompt_eval_count")),
            output_tokens=_count(reply.get("eval_count")),
            is_local=True,
        ),
    )


def _count(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _context_tokens(prompt: str, max_tokens: int) -> int:
    """A context window that fits the prompt and the reply.

    Ollama silently drops the start of a prompt that overflows its default window,
    so it is sized per request. Powers of two keep the number of distinct sizes
    small, because Ollama reloads the model whenever the size changes.
    """
    needed = len(prompt) // CHARS_PER_TOKEN + max_tokens
    return max(MIN_CONTEXT_TOKENS, 1 << (needed - 1).bit_length())


def _is_installed(model: str, installed: list[InstalledModel]) -> bool:
    # Ollama stores an untagged name as `<name>:latest`.
    wanted = model if ":" in model else f"{model}:latest"
    return any(item.name == wanted for item in installed)


def _not_pulled(model: str) -> ModelError:
    return ModelError(
        f"Ollama model '{model}' is not pulled.", hint=f"Run `ollama pull {model}`."
    )
