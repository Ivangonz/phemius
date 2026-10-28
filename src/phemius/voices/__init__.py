"""Voice engines, selected with PHEMIUS_TTS.

Adding an engine means adding one module and one line to `ENGINES`.
"""

from collections.abc import Callable
from functools import lru_cache

from phemius.config import Config
from phemius.errors import VoiceError
from phemius.voices.base import Voice, VoiceCheck, VoiceEngine, namespace_voice
from phemius.voices.kokoro import KokoroEngine
from phemius.voices.stub import StubEngine

__all__ = [
    "ENGINES",
    "Voice",
    "VoiceCheck",
    "VoiceEngine",
    "get_engine",
    "namespace_voice",
]

ENGINES: dict[str, Callable[[], VoiceEngine]] = {
    "kokoro": KokoroEngine,
    "stub": StubEngine,
}


def get_engine(config: Config) -> VoiceEngine:
    """The configured engine. Raises `VoiceError` for an unknown engine name."""
    return _engine_named(config.voice_engine)


# Engines are cached so heavy models (one KPipeline per accent) load only once.
@lru_cache(maxsize=len(ENGINES))
def _engine_named(name: str) -> VoiceEngine:
    if name not in ENGINES:
        raise VoiceError(
            f"Unknown voice engine '{name}'.",
            hint=f"Set PHEMIUS_TTS to one of: {', '.join(ENGINES)}.",
        )
    return ENGINES[name]()
