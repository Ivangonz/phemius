"""Describe the configured script model for the UI and the setup checks."""

from dataclasses import dataclass

from phemius.config import load_config
from phemius.errors import ModelError
from phemius.models import get_script_model


@dataclass(frozen=True)
class ActiveScriptModel:
    """The provider and model that write scripts; never holds secrets."""

    provider: str
    model: str
    error: str | None = None
    hint: str | None = None


def active_model() -> ActiveScriptModel:
    """The configured adapter's model, or why the adapter cannot be built."""
    config = load_config()
    try:
        model = get_script_model(config)
    except ModelError as error:
        # Ollama and the offline rules always build; the adapters that can fail (a
        # missing key or base URL) all read PHEMIUS_MODEL.
        return ActiveScriptModel(
            provider=config.script_provider,
            model=config.model,
            error=error.message,
            hint=error.hint,
        )
    return ActiveScriptModel(provider=config.script_provider, model=model.model)
