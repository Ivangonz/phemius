"""Any server that speaks the OpenAI chat completions API.

One adapter covers OpenAI, OpenRouter and self-hosted servers such as LM Studio,
vLLM and LiteLLM. The `openai` and `openrouter` presets fill in only the base URL
and which key to read.
"""

from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

import structlog
from openai import (
    DEFAULT_MAX_RETRIES,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    DefaultHttpxClient,
    OpenAI,
)
from openai.types.chat import ChatCompletion
from pydantic import SecretStr

from phemius.config import Config
from phemius.errors import ModelError
from phemius.models.base import TokenUsage
from phemius.models.chat import ChatReply, ChatScriptModel

log = structlog.get_logger(__name__)

OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Local servers ignore the key, but the OpenAI client refuses to start without one
# and would otherwise read OPENAI_API_KEY and send it to whatever server this is.
NO_KEY = "no-key"


@dataclass(frozen=True)
class Provider:
    """How errors name the provider, its key and what to check when unreachable."""

    name: str
    key_env: str
    connect_hint: str


OPENAI = Provider("OpenAI", "OPENAI_API_KEY", "Check your network connection.")
OPENROUTER = Provider(
    "OpenRouter", "OPENROUTER_API_KEY", "Check your network connection."
)


class OpenAICompatibleModel(ChatScriptModel):
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        script_max_tokens: int,
        *,
        provider: Provider | None = None,
        http_client: DefaultHttpxClient | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        super().__init__(model, script_max_tokens)
        self.base_url = base_url
        self.provider = provider or _server_provider(base_url)
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key or NO_KEY,
            http_client=http_client,
            max_retries=max_retries,
        )

    def _chat(self, system: str, user: str, max_tokens: int) -> ChatReply:
        completion = self._request(system, user, max_tokens)
        choice = completion.choices[0]
        return ChatReply(
            content=choice.message.content or "",
            is_truncated=choice.finish_reason == "length",
            usage=_token_usage(completion),
        )

    def _request(self, system: str, user: str, max_tokens: int) -> ChatCompletion:
        log.debug("model_request", provider=self.provider.name, model=self.model)
        try:
            return self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except (APIStatusError, APIConnectionError) as error:
            model_error = _model_error(error, self.provider)
            log.warning(
                "model_request_failed",
                provider=self.provider.name,
                model=self.model,
                error=model_error.message,
            )
            raise model_error from error


def _token_usage(completion: ChatCompletion) -> TokenUsage:
    usage = completion.usage
    if usage is None:
        return TokenUsage()
    # `cost` is not in the OpenAI schema; OpenRouter adds it, in US dollars.
    cost = (usage.model_extra or {}).get("cost")
    return TokenUsage(
        input_tokens=usage.prompt_tokens,
        output_tokens=usage.completion_tokens,
        provider_cost_usd=_price(cost),
    )


def _price(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _model_error(
    error: APIStatusError | APIConnectionError, provider: Provider
) -> ModelError:
    # Provider messages can echo part of the key, so errors carry only the status.
    if isinstance(error, APIStatusError):
        return ModelError(
            f"{provider.name} returned {error.status_code}.",
            hint=_status_hint(error.status_code, provider),
        )
    if isinstance(error, APITimeoutError):
        return ModelError(
            f"{provider.name} did not answer in time.",
            hint="The model may still be loading or the server is busy; try again"
            " or use a smaller model.",
        )
    return ModelError(f"Could not reach {provider.name}.", hint=provider.connect_hint)


def _status_hint(status_code: int, provider: Provider) -> str | None:
    return {
        401: f"Check {provider.key_env}.",
        402: f"Add credits with {provider.name} or lower PHEMIUS_SCRIPT_MAX_TOKENS.",
        404: f"Check that PHEMIUS_MODEL names a model {provider.name} serves"
        " and that the base URL is right.",
        429: f"{provider.name} is rate limiting requests or the account is out of"
        " quota; try again in a minute.",
    }.get(status_code)


def _server_provider(base_url: str) -> Provider:
    # Name the server by host and port; the URL may carry credentials.
    host = urlsplit(base_url).netloc.rpartition("@")[2]
    return Provider(
        host or "the OpenAI-compatible server",
        "PHEMIUS_SCRIPT_API_KEY",
        "Check that the server is running and PHEMIUS_SCRIPT_BASE_URL is right.",
    )


def from_config(config: Config) -> OpenAICompatibleModel:
    if config.script_base_url is None:
        raise ModelError(
            "The openai_compatible provider needs a base URL.",
            hint="Set PHEMIUS_SCRIPT_BASE_URL, for example http://localhost:1234/v1.",
        )
    return _cached_model(
        config.script_base_url,
        _reveal(config.script_api_key),
        config.model,
        config.script_max_tokens,
        None,
    )


def openai_from_config(config: Config) -> OpenAICompatibleModel:
    return _preset(config, OPENAI_BASE_URL, OPENAI, config.openai_api_key)


def openrouter_from_config(config: Config) -> OpenAICompatibleModel:
    return _preset(config, OPENROUTER_BASE_URL, OPENROUTER, config.openrouter_api_key)


def _preset(
    config: Config, base_url: str, provider: Provider, api_key: SecretStr | None
) -> OpenAICompatibleModel:
    if api_key is None:
        raise ModelError(
            f"{provider.name} needs an API key.",
            hint=f"Set {provider.key_env}, or set PHEMIUS_SCRIPT_PROVIDER=offline.",
        )
    return _cached_model(
        base_url,
        api_key.get_secret_value(),
        config.model,
        config.script_max_tokens,
        provider,
    )


def _reveal(api_key: SecretStr | None) -> str | None:
    return api_key.get_secret_value() if api_key else None


@lru_cache(maxsize=4)
def _cached_model(
    base_url: str,
    api_key: str | None,
    model: str,
    script_max_tokens: int,
    provider: Provider | None,
) -> OpenAICompatibleModel:
    return OpenAICompatibleModel(
        base_url, api_key, model, script_max_tokens, provider=provider
    )
