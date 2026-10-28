"""OpenRouter chat completions through the OpenAI-compatible client."""

from functools import lru_cache

from openai import APIConnectionError, APIStatusError, DefaultHttpxClient, OpenAI
from openai.types.chat import ChatCompletion

from phemius.config import Config
from phemius.errors import ModelError
from phemius.models.chat import ChatReply, ChatScriptModel

BASE_URL = "https://openrouter.ai/api/v1"

# Provider messages can echo part of the key, so errors carry only the status.
STATUS_HINTS = {
    401: "Check OPENROUTER_API_KEY.",
    402: "Add OpenRouter credits or lower PHEMIUS_SCRIPT_MAX_TOKENS.",
    404: "Check that PHEMIUS_MODEL is a model slug listed on openrouter.ai/models.",
    429: "OpenRouter is rate limiting requests; try again in a minute.",
}


class OpenRouterModel(ChatScriptModel):
    length_hint = (
        "Raise PHEMIUS_SCRIPT_MAX_TOKENS (needs more OpenRouter credit)"
        " or use a shorter document."
    )

    def __init__(
        self,
        api_key: str,
        model: str,
        script_max_tokens: int,
        http_client: DefaultHttpxClient | None = None,
    ) -> None:
        super().__init__(model, script_max_tokens)
        self._client = OpenAI(
            base_url=BASE_URL, api_key=api_key, http_client=http_client
        )

    def _chat(self, system: str, user: str, max_tokens: int) -> ChatReply:
        choice = self._request(system, user, max_tokens).choices[0]
        return ChatReply(
            content=choice.message.content or "",
            is_truncated=choice.finish_reason == "length",
        )

    def _request(self, system: str, user: str, max_tokens: int) -> ChatCompletion:
        try:
            return self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except APIStatusError as error:
            raise ModelError(
                f"OpenRouter returned {error.status_code}.",
                hint=STATUS_HINTS.get(error.status_code),
            ) from error
        except APIConnectionError as error:
            raise ModelError(
                "Could not reach OpenRouter.", hint="Check your network connection."
            ) from error


def from_config(config: Config) -> OpenRouterModel:
    if not config.openrouter_api_key:
        raise ModelError(
            "OpenRouter needs an API key.",
            hint="Set OPENROUTER_API_KEY, or set PHEMIUS_SCRIPT_PROVIDER=offline.",
        )
    return _cached_model(
        config.openrouter_api_key, config.model, config.script_max_tokens
    )


@lru_cache(maxsize=4)
def _cached_model(api_key: str, model: str, script_max_tokens: int) -> OpenRouterModel:
    return OpenRouterModel(api_key, model, script_max_tokens)
