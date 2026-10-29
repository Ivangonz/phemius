from collections.abc import Callable

from phemius.errors import ModelError
from phemius.models.base import (
    Analysis,
    AudioSuitability,
    Script,
    ScriptModel,
    ScriptModelCheck,
    TokenUsage,
)

type UseScriptModel = Callable[[ScriptModel], None]


class FakeScriptModel:
    model = "fake/model"

    def __init__(
        self,
        script: str = "A fake spoken script.",
        suitability: AudioSuitability = "recommended",
        usage: TokenUsage | None = None,
    ) -> None:
        self.script = script
        self.suitability: AudioSuitability = suitability
        self.usage = usage or TokenUsage()
        self.analyze_calls = 0

    def analyze(self, title: str, text: str) -> Analysis:
        self.analyze_calls += 1
        return Analysis(
            category="proposal / spec",
            summary=f"Fake summary of {title}.",
            suggested_tone="podcast",
            tone_rationale="Fake rationale for the podcast tone.",
            audio_suitability=self.suitability,
            suitability_reason=f"Fake reason it is {self.suitability}.",
            suitability_source="model",
        )

    def write_script(self, title: str, text: str, tone: str) -> Script:
        return Script(self.script, self.usage)

    def check(self) -> ScriptModelCheck:
        return ScriptModelCheck(is_reachable=True, model=self.model, latency_ms=1.0)


class FailingScriptModel(FakeScriptModel):
    error = ModelError("Provider returned 402.", hint="Add provider credits.")

    def analyze(self, title: str, text: str) -> Analysis:
        raise self.error

    def write_script(self, title: str, text: str, tone: str) -> Script:
        raise self.error


class RecordingScriptModel(FakeScriptModel):
    """Keeps the text each script request received."""

    def __init__(self, script: str = "A fake spoken script.") -> None:
        super().__init__(script)
        self.script_texts: list[str] = []

    def write_script(self, title: str, text: str, tone: str) -> Script:
        self.script_texts.append(text)
        return super().write_script(title, text, tone)
