"""OpenRouter chat completions through the OpenAI-compatible client."""

from functools import lru_cache

from openai import OpenAI

from phemius.errors import ModelError

BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterClient:
    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        self._client = OpenAI(base_url=BASE_URL, api_key=api_key)

    def complete(self, system: str, user: str, max_tokens: int) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice = response.choices[0]
        if choice.finish_reason == "length":
            # Never silently ship a script that was cut off mid-document.
            raise ModelError(
                f"Model output hit the {max_tokens}-token limit.",
                hint="Raise PHEMIUS_SCRIPT_MAX_TOKENS (needs more OpenRouter credit)"
                " or use a shorter document.",
            )
        return choice.message.content or ""


@lru_cache(maxsize=4)
def get_client(api_key: str, model: str) -> OpenRouterClient:
    return OpenRouterClient(api_key, model)
