"""The interface every script model adapter implements."""

from dataclasses import dataclass
from typing import Protocol, TypedDict


class Analysis(TypedDict):
    category: str
    summary: str
    suggested_tone: str


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
