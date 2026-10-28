"""Configuration read from `PHEMIUS_*` environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path

ENV_PREFIX = "PHEMIUS_"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"
OFFLINE_PROVIDER = "offline"


@dataclass(frozen=True)
class Config:
    data_dir: Path
    model: str
    voice_engine: str
    default_voice: str | None  # None means the engine's first voice
    watch_dir: Path | None
    output_format: str
    script_max_tokens: int
    log_level: str
    script_provider: str
    openrouter_api_key: str | None = field(default=None, repr=False)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "library.db"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


def read_env(name: str) -> str | None:
    return os.environ.get(ENV_PREFIX + name) or None


def _optional_path(value: str | None) -> Path | None:
    return Path(value).expanduser() if value else None


def _default_script_provider(openrouter_api_key: str | None) -> str:
    # Existing installs only set the key, so it keeps selecting OpenRouter.
    return "openrouter" if openrouter_api_key else OFFLINE_PROVIDER


def load_config() -> Config:
    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY") or None
    return Config(
        data_dir=_optional_path(read_env("DATA_DIR")) or Path.home() / ".phemius",
        model=read_env("MODEL") or DEFAULT_MODEL,
        voice_engine=(read_env("TTS") or "kokoro").lower(),
        default_voice=read_env("VOICE"),
        watch_dir=_optional_path(read_env("WATCH_DIR")),
        output_format=(read_env("FORMAT") or "wav").lower(),
        script_max_tokens=int(read_env("SCRIPT_MAX_TOKENS") or "8000"),
        log_level=(read_env("LOG_LEVEL") or "info").upper(),
        script_provider=(
            read_env("SCRIPT_PROVIDER") or _default_script_provider(openrouter_api_key)
        ).lower(),
        openrouter_api_key=openrouter_api_key,
    )
