"""The voice engine protocol and the types every engine shares."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

SAMPLE_TEXT = "Hi there. This is how your documentation will sound."


@dataclass(frozen=True)
class Voice:
    """A voice an engine offers. `id` is namespaced, for example `kokoro:af_heart`."""

    id: str
    label: str
    accent: str | None
    sample_text: str = SAMPLE_TEXT


@dataclass(frozen=True)
class VoiceCheck:
    """Whether an engine can synthesize right now, and how to fix it if not."""

    is_ready: bool
    message: str
    hint: str | None = None


class VoiceEngine(Protocol):
    extension: str

    def voices(self) -> list[Voice]:
        """The engine's voices, default first."""
        ...

    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        """Write narrated audio for `script` using the namespaced `voice` id."""
        ...

    def check(self) -> VoiceCheck: ...


def namespace_voice(engine_name: str, voice: str) -> str:
    """Prefix a bare voice id such as `af_heart` with its engine name."""
    return voice if ":" in voice else f"{engine_name}:{voice}"
