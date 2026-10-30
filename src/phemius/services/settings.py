"""Read and save settings for the Settings screens. Secrets are write-only."""

import structlog
from pydantic import BaseModel, SecretStr

from phemius.config import (
    Config,
    Settings,
    SettingSource,
    configured_values,
    env_override,
    load_config,
    setting_env,
)
from phemius.errors import InvalidSettingError, SettingLockedError
from phemius.models.prompts import TONES
from phemius.services import voices
from phemius.store import settings as settings_store

log = structlog.get_logger(__name__)

type SettingValue = str | int | float | bool | None


class SettingStatus(BaseModel):
    value: SettingValue
    source: SettingSource
    is_locked: bool


class SecretStatus(BaseModel):
    has_key: bool
    source: SettingSource
    is_locked: bool


class SettingsOverview(BaseModel):
    values: dict[str, SettingStatus]
    secrets: dict[str, SecretStatus]


def describe_settings() -> SettingsOverview:
    values = load_config().model_dump(mode="json")
    configured_by_key = configured_values()
    overview = SettingsOverview(values={}, secrets={})
    for key in Settings.model_fields:
        configured = configured_by_key[key]
        is_locked = configured.source == "env"
        if setting_env(key).is_secret:
            overview.secrets[key] = SecretStatus(
                has_key=values[key] is not None,
                source=configured.source,
                is_locked=is_locked,
            )
        else:
            overview.values[key] = SettingStatus(
                value=values[key], source=configured.source, is_locked=is_locked
            )
    return overview


def update_settings(update: Settings) -> None:
    """Save the fields set in `update`. `None` removes the saved value."""
    keys = sorted(update.model_fields_set)
    _reject_locked(keys)
    _reject_unknown_defaults(update)
    settings_store.save_settings({key: _storable(update, key) for key in keys})
    log.info("settings_updated", keys=keys)


def _reject_locked(keys: list[str]) -> None:
    locked = {
        key: f"Set by environment variable {setting_env(key).name}"
        for key in keys
        if env_override(key) is not None
    }
    if locked:
        raise SettingLockedError(
            "Some settings are set by environment variables.",
            hint="Unset the variable and restart to change it here.",
            field_errors=locked,
        )


def _reject_unknown_defaults(update: Settings) -> None:
    unknown: dict[str, str] = {}
    if "default_tone" in update.model_fields_set and update.default_tone not in TONES:
        unknown["default_tone"] = f"Choose one of: {', '.join(TONES)}."
    if update.default_voice is not None:
        config = _config_with_engine_of(update)
        if not voices.is_known_voice(update.default_voice, config):
            unknown["default_voice"] = f"Not a {config.voice_engine} voice."
    if unknown:
        raise InvalidSettingError(
            "Some settings are not offered by this library.", field_errors=unknown
        )


def _config_with_engine_of(update: Settings) -> Config:
    # The same update may switch the engine; check the voice against that one.
    config = load_config()
    if "voice_engine" in update.model_fields_set:
        return config.model_copy(update={"voice_engine": update.voice_engine})
    return config


def _storable(update: Settings, key: str) -> object:
    value = getattr(update, key)
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return update.model_dump(mode="json", include={key})[key]
