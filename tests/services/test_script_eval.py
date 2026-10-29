"""The spoken-script evaluation set. See docs/script-evaluation.md."""

import os
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from phemius.models.spoken_text import CODE_EXAMPLE
from phemius.services import agent
from phemius.services.ingest import guess_title
from tests.models.fakes import RecordingScriptModel, UseScriptModel

EVAL_DIR = Path(__file__).parents[1] / "fixtures" / "script_eval"
# Read at import, before the autouse fixture clears the model settings per test.
LIVE_ENVIRONMENT = {
    name: value
    for name, value in os.environ.items()
    if name.startswith("PHEMIUS_") or name.endswith("_API_KEY")
}
KEPT_LIVE_SETTINGS = {"PHEMIUS_DATA_DIR", "PHEMIUS_TTS"}
IS_LIVE = os.environ.get("PHEMIUS_EVAL_LIVE") == "1"

MODEL_INPUT_MARKUP = re.compile(r"```|~~~|\||\]\(|!\[|^\s*\[[^\]]+\]:", re.M)
MARKDOWN_SYMBOL = re.compile(r"[`*|\[\]]|^\s*[#>]|^\s*[-+]\s", re.M)
RAW_URL = re.compile(r"https?://|www\.")


@dataclass(frozen=True)
class EvalCase:
    name: str
    kept_phrases: tuple[str, ...]
    min_ratio: float = 0.3
    max_ratio: float = 2.5

    @property
    def source(self) -> str:
        return (EVAL_DIR / f"{self.name}.md").read_text(encoding="utf-8")


CASES = [
    EvalCase("code_blocks", ("uv run worker status", "Stop the other process")),
    EvalCase("tables", ("Engine: Piper", "Runs offline: no", "Default: m4a")),
    EvalCase("links", ("installation guide", "troubleshooting notes")),
    EvalCase("acronyms", ("gateway.yaml", "OIDC", "README.md")),
    EvalCase("narrative", ("consolidated on one database",), min_ratio=0.9),
]
CASE_IDS = [case.name for case in CASES]


def write_script(case: EvalCase) -> str:
    script = agent.make_script(
        guess_title(case.source, case.name), case.source, "neutral"
    )
    assert script is not None
    return script.text


def assert_speakable(script: str, case: EvalCase) -> None:
    assert not MARKDOWN_SYMBOL.findall(script)
    assert not RAW_URL.findall(script)
    ratio = len(script) / len(case.source)
    assert case.min_ratio <= ratio <= case.max_ratio, f"length ratio {ratio:.2f}"


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_model_receives_speakable_input(
    case: EvalCase, use_script_model: UseScriptModel
) -> None:
    model = RecordingScriptModel()
    use_script_model(model)

    write_script(case)

    [sent] = model.script_texts
    prose = CODE_EXAMPLE.sub("", sent)
    assert not MODEL_INPUT_MARKUP.findall(prose)
    assert not RAW_URL.findall(prose)
    assert all(phrase in sent for phrase in case.kept_phrases)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_offline_script_is_speakable(case: EvalCase) -> None:
    assert_speakable(write_script(case), case)


@pytest.mark.live_model
@pytest.mark.skipif(not IS_LIVE, reason="set PHEMIUS_EVAL_LIVE=1 to call a model")
@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_live_model_script_is_speakable(
    case: EvalCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in LIVE_ENVIRONMENT.items():
        if name not in KEPT_LIVE_SETTINGS:
            monkeypatch.setenv(name, value)

    script = write_script(case)

    print(f"\n--- {case.name} ---\n{script}")
    assert_speakable(script, case)
