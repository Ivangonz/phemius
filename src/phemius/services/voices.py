"""Choose and validate voices for the configured voice engine."""

from phemius.config import Config, load_config
from phemius.errors import InvalidInputError, VoiceError
from phemius.voices import Voice, VoiceCheck, get_engine, namespace_voice


def list_voices() -> list[Voice]:
    """The configured engine's voices, or none when the engine is unknown."""
    try:
        return get_engine(load_config()).voices()
    except VoiceError:
        return []


def check_engine() -> VoiceCheck:
    """Whether the configured engine can synthesize, with a hint when it cannot."""
    try:
        return get_engine(load_config()).check()
    except VoiceError as error:
        return VoiceCheck(is_ready=False, message=error.message, hint=error.hint)


def resolve_voice(requested: str | None = None) -> str:
    """The namespaced id of `requested`, or of the default voice when it is None.

    Bare ids such as `af_heart` are namespaced with the configured engine.
    """
    config = load_config()
    available = [voice.id for voice in get_engine(config).voices()]
    if requested is None:
        return _default_voice(config, available)
    voice_id = namespace_voice(config.voice_engine, requested)
    if voice_id not in available:
        raise InvalidInputError(
            f"Unknown voice; choose from {available}", field="voice"
        )
    return voice_id


def default_voice() -> str | None:
    """The default voice id, or None when the engine or PHEMIUS_VOICE is invalid."""
    try:
        return resolve_voice()
    except VoiceError:
        return None


def _default_voice(config: Config, available: list[str]) -> str:
    if config.default_voice is None:
        return available[0]
    voice_id = namespace_voice(config.voice_engine, config.default_voice)
    if voice_id not in available:
        raise VoiceError(
            f"PHEMIUS_VOICE '{config.default_voice}' is not a"
            f" {config.voice_engine} voice.",
            hint=f"Set PHEMIUS_VOICE to one of: {', '.join(available)}.",
        )
    return voice_id
