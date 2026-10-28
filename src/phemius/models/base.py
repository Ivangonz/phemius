"""The interface every script model adapter implements."""

from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict

type AudioSuitability = Literal["recommended", "partial", "not_recommended"]
# Who judged suitability: the script model, or the offline rules when there is no
# model, the model failed, or its reply had no valid verdict.
type SuitabilitySource = Literal["model", "heuristic"]


class Analysis(TypedDict):
    category: str
    summary: str
    suggested_tone: str
    tone_rationale: str
    audio_suitability: AudioSuitability
    suitability_reason: str
    suitability_source: SuitabilitySource


@dataclass(frozen=True)
class ScriptModelCheck:
    """Result of a connection check, safe to show in the UI (never holds secrets)."""

    is_reachable: bool
    model: str
    latency_ms: float | None = None
    error: str | None = None
    hint: str | None = None


class ScriptModel(Protocol):
    """Categorizes documents and writes spoken scripts.

    Provider failures raise `ModelError` with a hint; output is never truncated.
    """

    @property
    def model(self) -> str:
        """The name of the model that writes scripts, safe to show in the UI."""
        ...

    def analyze(self, title: str, text: str) -> Analysis: ...

    def write_script(self, title: str, text: str, tone: str) -> str: ...

    def check(self) -> ScriptModelCheck: ...
