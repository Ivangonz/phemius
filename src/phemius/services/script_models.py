"""Describe, test and list the script models for the UI and the setup checks."""

from dataclasses import dataclass

import structlog
from pydantic import BaseModel

from phemius.config import OFFLINE_PROVIDER, load_config
from phemius.errors import ModelError
from phemius.models import get_script_model, ollama

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ActiveScriptModel:
    """The provider and model that write scripts; never holds secrets."""

    provider: str
    model: str
    error: str | None = None
    hint: str | None = None


class ScriptModelConnection(BaseModel):
    """The result of testing the saved script model; never holds secrets."""

    is_reachable: bool
    provider: str
    model: str
    latency_ms: float | None = None
    error: str | None = None
    hint: str | None = None


class InstalledOllamaModel(BaseModel):
    name: str
    size_bytes: int


class OllamaModelList(BaseModel):
    models: list[InstalledOllamaModel]


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


def check_connection() -> ScriptModelConnection:
    """Send the saved script model a short request; offline rules need none."""
    active = active_model()
    connection = ScriptModelConnection(
        is_reachable=active.error is None,
        provider=active.provider,
        model=active.model,
        error=active.error,
        hint=active.hint,
    )
    if connection.is_reachable and active.provider != OFFLINE_PROVIDER:
        result = get_script_model(load_config()).check()
        connection = connection.model_copy(
            update={
                "is_reachable": result.is_reachable,
                "latency_ms": result.latency_ms,
                "error": result.error,
                "hint": result.hint,
            }
        )
    log.info(
        "script_model_checked",
        provider=connection.provider,
        model=connection.model,
        is_reachable=connection.is_reachable,
        latency_ms=connection.latency_ms,
    )
    return connection


def list_ollama_models() -> OllamaModelList:
    """Models pulled into the saved Ollama server; raises ModelError if unreachable."""
    installed = ollama.from_config(load_config()).list_models()
    return OllamaModelList(
        models=[
            InstalledOllamaModel(name=item.name, size_bytes=item.size_bytes)
            for item in installed
        ]
    )
