from collections.abc import Callable

from phemius.errors import ModelError
from phemius.models.base import Analysis, ScriptModel, ScriptModelCheck

type UseScriptModel = Callable[[ScriptModel], None]


class FakeScriptModel:
    def __init__(self, script: str = "A fake spoken script.") -> None:
        self.script = script
        self.analyze_calls = 0

    def analyze(self, title: str, text: str) -> Analysis:
        self.analyze_calls += 1
        return Analysis(
            category="proposal / spec",
            summary=f"Fake summary of {title}.",
            suggested_tone="podcast",
        )

    def write_script(self, title: str, text: str, tone: str) -> str:
        return self.script

    def check(self) -> ScriptModelCheck:
        return ScriptModelCheck(is_reachable=True, model="fake/model", latency_ms=1.0)


class FailingScriptModel(FakeScriptModel):
    error = ModelError("Provider returned 402.", hint="Add provider credits.")

    def analyze(self, title: str, text: str) -> Analysis:
        raise self.error

    def write_script(self, title: str, text: str, tone: str) -> str:
        raise self.error
