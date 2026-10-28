"""Voice engines, selected with PHEMIUS_TTS.

Adding an engine means adding one module with a `from_config` factory and one
line to `ENGINES`.
"""

from collections.abc import Callable

from phemius.config import Config
from phemius.errors import VoiceError
from phemius.voices import elevenlabs, kokoro, openai_speech, stub
from phemius.voices.base import Voice, VoiceCheck, VoiceEngine, namespace_voice

__all__ = [
    "ENGINES",
    "Voice",
    "VoiceCheck",
    "VoiceEngine",
    "get_engine",
    "namespace_voice",
]

type VoiceEngineFactory = Callable[[Config], VoiceEngine]

ENGINES: dict[str, VoiceEngineFactory] = {
    "kokoro": kokoro.from_config,
    "stub": stub.from_config,
    "openai_speech": openai_speech.from_config,
    "elevenlabs": elevenlabs.from_config,
}


def get_engine(config: Config) -> VoiceEngine:
    """The configured engine. Raises `VoiceError` for an unknown engine name."""
    factory = ENGINES.get(config.voice_engine)
    if factory is None:
        raise VoiceError(
            f"Unknown voice engine '{config.voice_engine}'.",
            hint=f"Set PHEMIUS_TTS to one of: {', '.join(ENGINES)}.",
        )
    return factory(config)
