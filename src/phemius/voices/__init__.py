"""Voice engines. Select one with PHEMIUS_TTS (kokoro or stub)."""

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from phemius.voices.kokoro import VOICES, KokoroEngine
from phemius.voices.stub import StubEngine

__all__ = ["VOICES", "VoiceEngine", "get_engine"]


class VoiceEngine(Protocol):
    extension: str

    def synthesize(self, script: str, out_path: Path, voice: str) -> None: ...


@lru_cache(maxsize=2)
def get_engine(name: str) -> VoiceEngine:
    return StubEngine() if name == "stub" else KokoroEngine()
