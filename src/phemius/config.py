"""Configuration: environment variable, then saved setting, then default.

The data folder and log level come only from `PHEMIUS_*` environment variables,
because the database that holds saved settings lives in the data folder.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
)

from phemius.errors import PhemiusError
from phemius.store import database
from phemius.store import settings as settings_store
from phemius.store.jobs import AudioFormat

ENV_PREFIX = "PHEMIUS_"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"
OFFLINE_PROVIDER = "offline"

type SettingSource = Literal["env", "saved", "default"]
type AccessMode = Literal["local", "network", "proxy"]
type WatchOnChange = Literal["mark", "regenerate"]


@dataclass(frozen=True)
class EnvVar:
    """Settings field metadata: the environment variable that overrides it."""

    name: str
    is_secret: bool = False


def _lower(value: object) -> object:
    return value.lower() if isinstance(value, str) else value


def _output_format(value: object) -> object:
    # `mp4` was an output format before M4A replaced it; both are AAC in an MPEG-4
    # container, so a saved or exported `mp4` keeps working as `m4a`.
    value = _lower(value)
    return "m4a" if value == "mp4" else value


def _expand_user(path: Path | None) -> Path | None:
    return path.expanduser() if path else None


def _comma_list(value: str) -> str:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise ValueError("List at least one id, separated by commas.")
    return ",".join(items)


# Stored as one comma-separated string so it reads the same from an environment
# variable and fits the scalar values of the settings API.
type CommaList = Annotated[str, AfterValidator(_comma_list)]


class Settings(BaseModel):
    """Options a user can save. Adding one is one field here, with its `EnvVar`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: Annotated[str, Field(min_length=1), EnvVar("PHEMIUS_MODEL")] = DEFAULT_MODEL
    voice_engine: Annotated[
        str, BeforeValidator(_lower), Field(min_length=1), EnvVar("PHEMIUS_TTS")
    ] = "kokoro"
    script_provider: Annotated[
        Annotated[str, BeforeValidator(_lower), Field(min_length=1)] | None,
        EnvVar("PHEMIUS_SCRIPT_PROVIDER"),
    ] = None
    # None means the engine's first voice; resolve_voice namespaces a bare id.
    default_voice: Annotated[
        Annotated[str, Field(min_length=1)] | None, EnvVar("PHEMIUS_VOICE")
    ] = None
    watch_dir: Annotated[
        Path | None, AfterValidator(_expand_user), EnvVar("PHEMIUS_WATCH_DIR")
    ] = None
    # "mark" by default: editors save often, and regenerating on every save would
    # spend model credits and voice time on drafts.
    watch_on_change: Annotated[
        WatchOnChange, BeforeValidator(_lower), EnvVar("PHEMIUS_WATCH_ON_CHANGE")
    ] = "mark"
    # On by default: automatic imports exist to save clicks, not to spend model
    # credits and voice time on references nobody listens to. Manual "generate
    # audio" still works for a skipped document.
    skip_not_recommended: Annotated[bool, EnvVar("PHEMIUS_SKIP_NOT_RECOMMENDED")] = True
    output_format: Annotated[
        AudioFormat, BeforeValidator(_output_format), EnvVar("PHEMIUS_FORMAT")
    ] = "wav"
    script_max_tokens: Annotated[
        int, Field(gt=0), EnvVar("PHEMIUS_SCRIPT_MAX_TOKENS")
    ] = 8000
    # US dollars per million tokens, for estimating the cost of providers that do
    # not report one. Both are needed; they apply to whichever model is configured.
    script_input_price: Annotated[
        Annotated[float, Field(ge=0)] | None, EnvVar("PHEMIUS_SCRIPT_INPUT_PRICE")
    ] = None
    script_output_price: Annotated[
        Annotated[float, Field(ge=0)] | None, EnvVar("PHEMIUS_SCRIPT_OUTPUT_PRICE")
    ] = None
    # Read when the job runner starts, so a change applies on the next start.
    # Voices always render one at a time; this bounds parallel script writing.
    script_workers: Annotated[
        int, Field(ge=1, le=8), EnvVar("PHEMIUS_SCRIPT_WORKERS")
    ] = 2
    openrouter_api_key: Annotated[
        Annotated[SecretStr, Field(min_length=1)] | None,
        EnvVar("OPENROUTER_API_KEY", is_secret=True),
    ] = None
    openai_api_key: Annotated[
        Annotated[SecretStr, Field(min_length=1)] | None,
        EnvVar("OPENAI_API_KEY", is_secret=True),
    ] = None
    script_base_url: Annotated[
        Annotated[str, Field(pattern=r"^https?://\S+$")] | None,
        EnvVar("PHEMIUS_SCRIPT_BASE_URL"),
    ] = None
    script_api_key: Annotated[
        Annotated[SecretStr, Field(min_length=1)] | None,
        EnvVar("PHEMIUS_SCRIPT_API_KEY", is_secret=True),
    ] = None
    ollama_url: Annotated[str, Field(min_length=1), EnvVar("PHEMIUS_OLLAMA_URL")] = (
        "http://localhost:11434"
    )
    ollama_model: Annotated[
        str, Field(min_length=1), EnvVar("PHEMIUS_OLLAMA_MODEL")
    ] = "llama3.2"
    # Local models on a CPU can take minutes to write a long script.
    ollama_timeout: Annotated[int, Field(gt=0), EnvVar("PHEMIUS_OLLAMA_TIMEOUT")] = 600
    openai_speech_base_url: Annotated[
        str, Field(min_length=1), EnvVar("PHEMIUS_OPENAI_SPEECH_BASE_URL")
    ] = "https://api.openai.com/v1"
    openai_speech_api_key: Annotated[
        Annotated[SecretStr, Field(min_length=1)] | None,
        EnvVar("PHEMIUS_OPENAI_SPEECH_API_KEY", is_secret=True),
    ] = None
    openai_speech_model: Annotated[
        str, Field(min_length=1), EnvVar("PHEMIUS_OPENAI_SPEECH_MODEL")
    ] = "tts-1"
    openai_speech_voices: Annotated[
        CommaList, EnvVar("PHEMIUS_OPENAI_SPEECH_VOICES")
    ] = "alloy,ash,coral,echo,fable,nova,onyx,sage,shimmer"
    elevenlabs_api_key: Annotated[
        Annotated[SecretStr, Field(min_length=1)] | None,
        EnvVar("ELEVENLABS_API_KEY", is_secret=True),
    ] = None
    elevenlabs_voices: Annotated[CommaList, EnvVar("PHEMIUS_ELEVENLABS_VOICES")] = (
        "JBFqnCBsd6RMkjVDRZzb,EXAVITQu4vr4xnSDxMaL"
    )
    # Read once at startup: it decides the bind address and whether a token is
    # required, so a change applies on the next start.
    access_mode: Annotated[
        AccessMode, BeforeValidator(_lower), EnvVar("PHEMIUS_ACCESS_MODE")
    ] = "local"


class Config(Settings):
    data_dir: Path
    log_level: str
    # Always resolved by load_config; None is meaningful only in a settings update.
    script_provider: Annotated[str, BeforeValidator(_lower)]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "library.db"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


@dataclass(frozen=True)
class ConfiguredValue:
    source: SettingSource
    value: object = None


def read_env(name: str) -> str | None:
    return os.environ.get(ENV_PREFIX + name) or None


def setting_env(key: str) -> EnvVar:
    metadata = Settings.model_fields[key].metadata
    return next(item for item in metadata if isinstance(item, EnvVar))


def env_override(key: str) -> str | None:
    return os.environ.get(setting_env(key).name) or None


def configured_values() -> dict[str, ConfiguredValue]:
    """Each setting's unvalidated value and its source.

    Saved settings apply once `init_database()` has run; before that, and in
    tests that never open a library, only environment and defaults apply.
    """
    saved = settings_store.read_settings() if database.is_initialized() else {}
    return {key: _configured_value(key, saved) for key in Settings.model_fields}


def _configured_value(key: str, saved: dict[str, object]) -> ConfiguredValue:
    env_value = env_override(key)
    if env_value is not None:
        return ConfiguredValue("env", env_value)
    if key in saved:
        return ConfiguredValue("saved", saved[key])
    return ConfiguredValue("default")


def load_config() -> Config:
    configured = configured_values()
    explicit = {
        key: item.value for key, item in configured.items() if item.source != "default"
    }
    explicit.setdefault(
        "script_provider", _default_script_provider("openrouter_api_key" in explicit)
    )
    try:
        return Config.model_validate(
            {
                **explicit,
                "data_dir": Path(read_env("DATA_DIR") or "~/.phemius").expanduser(),
                "log_level": (read_env("LOG_LEVEL") or "info").upper(),
            }
        )
    except ValidationError as error:
        # `from None`: the validation error echoes its input, which may be a secret.
        raise _invalid_setting(error, configured) from None


def _default_script_provider(has_openrouter_key: bool) -> str:
    # Existing installs only set the key, so it keeps selecting OpenRouter.
    return "openrouter" if has_openrouter_key else OFFLINE_PROVIDER


def _invalid_setting(
    error: ValidationError, configured: dict[str, ConfiguredValue]
) -> PhemiusError:
    key = str(error.errors()[0]["loc"][0])
    hint = (
        f"Fix or unset {setting_env(key).name}."
        if configured[key].source == "env"
        else "Change it in Settings."
    )
    return PhemiusError(f"Setting {key} has an invalid value.", hint=hint, field=key)
