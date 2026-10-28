"""OpenRouter chat completions through the OpenAI-compatible client."""

from functools import lru_cache

from openai import APIConnectionError, APIStatusError, DefaultHttpxClient, OpenAI
from openai.types.chat import ChatCompletion

from phemius.errors import ModelError

BASE_URL = "https://openrouter.ai/api/v1"

# Provider messages can echo part of the key, so errors carry only the status.
STATUS_HINTS = {
    401: "Check OPENROUTER_API_KEY.",
    402: "Add OpenRouter credits or lower PHEMIUS_SCRIPT_MAX_TOKENS.",
    404: "Check that PHEMIUS_MODEL is a model slug listed on openrouter.ai/models.",
    429: "OpenRouter is rate limiting requests; try again in a minute.",
}


class OpenRouterClient:
    def __init__(
        self, api_key: str, model: str, http_client: DefaultHttpxClient | None = None
    ) -> None:
        self.model = model
        self._client = OpenAI(
            base_url=BASE_URL, api_key=api_key, http_client=http_client
        )

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        choice = self._request(system, user, max_tokens).choices[0]
        if choice.finish_reason == "length":
            # Never silently ship a script that was cut off mid-document.
            raise ModelError(
                f"Model output hit the {max_tokens}-token limit.",
                hint="Raise PHEMIUS_SCRIPT_MAX_TOKENS (needs more OpenRouter credit)"
                " or use a shorter document.",
            )
        return choice.message.content or ""

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


@lru_cache(maxsize=4)
def get_client(api_key: str, model: str) -> OpenRouterClient:
    return OpenRouterClient(api_key, model)
