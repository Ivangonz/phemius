"""Script model adapters. Select one with PHEMIUS_SCRIPT_PROVIDER.

Adding a provider means adding one adapter file with a `from_config` factory and
one line in `SCRIPT_MODELS`.
"""

from collections.abc import Callable

from phemius.config import OFFLINE_PROVIDER, Config
from phemius.errors import ModelError
from phemius.models import offline, openai_compatible
from phemius.models.base import ScriptModel

__all__ = ["OFFLINE_PROVIDER", "SCRIPT_MODELS", "get_script_model"]

type ScriptModelFactory = Callable[[Config], ScriptModel]

SCRIPT_MODELS: dict[str, ScriptModelFactory] = {
    OFFLINE_PROVIDER: offline.from_config,
    "openrouter": openai_compatible.openrouter_from_config,
    "openai": openai_compatible.openai_from_config,
    "openai_compatible": openai_compatible.from_config,
}


def get_script_model(config: Config) -> ScriptModel:
    factory = SCRIPT_MODELS.get(config.script_provider)
    if factory is None:
        raise ModelError(
            f"Unknown script provider '{config.script_provider}'.",
            hint=f"Set PHEMIUS_SCRIPT_PROVIDER to one of: {', '.join(SCRIPT_MODELS)}.",
        )
    return factory(config)
