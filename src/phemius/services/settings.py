"""Read and save settings for the Settings screens. Secrets are write-only."""

import structlog
from pydantic import BaseModel, SecretStr

from phemius.config import (
    Settings,
    SettingSource,
    configured_values,
    env_override,
    load_config,
    setting_env,
)
from phemius.errors import SettingLockedError
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
    overview = SettingsOverview(values={}, secrets={})
    for key, configured in configured_values().items():
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


def _storable(update: Settings, key: str) -> object:
    value = getattr(update, key)
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return update.model_dump(mode="json", include={key})[key]
