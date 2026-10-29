"""Categorizes documents and writes their spoken scripts with the configured model.

With no model configured the offline rules do both. A configured model that fails a
script raises `ModelError` so the audio fails with a hint; it never falls back to an
offline script. A failed analysis falls back to the rules, and the error is kept in
`last_error` so the UI can show it.
"""

from collections.abc import Callable
from dataclasses import dataclass

import structlog

from phemius.config import load_config
from phemius.errors import ModelError
from phemius.models import get_script_model
from phemius.models.base import (
    Analysis,
    SectionContext,
    TokenUsage,
)
from phemius.models.offline import OfflineModel
from phemius.models.sections import (
    Section,
    continuity,
    section_limit,
    split_sections,
)
from phemius.models.spoken_text import to_spoken_text
from phemius.services.usage import total_usage
from phemius.store.jobs import ScriptSection

log = structlog.get_logger(__name__)

# Most recent analysis failure, shown in the UI so a bad key or model is not silent.
last_error: str | None = None


def analyze(title: str, text: str) -> Analysis:
    try:
        return get_script_model(load_config()).analyze(title, text)
    except (ModelError, ValueError) as error:  # analysis may fall back (#23)
        _record_analysis_failure(error)
    return OfflineModel().analyze(title, text)


@dataclass(frozen=True)
class WrittenScript:
    sections: list[ScriptSection]
    usage: TokenUsage

    @property
    def text(self) -> str:
        return "\n\n".join(section.script for section in self.sections)


def _always() -> bool:
    return True


def make_script(
    title: str,
    text: str,
    tone: str,
    summary: str = "",
    should_continue: Callable[[], bool] = _always,
) -> WrittenScript | None:
    """Write a spoken script, section by section when the document is long.

    Returns None when `should_continue` turns false before a section. Raises
    `ModelError` if the configured model fails. Every model gets the same
    speakable input: code marked, tables flattened, URLs and images removed.
    """
    config = load_config()
    model = get_script_model(config)
    limit = section_limit(config.script_max_tokens)
    sections = split_sections(title, to_spoken_text(text), limit)
    written: list[ScriptSection] = []
    usages: list[TokenUsage] = []
    for number, section in enumerate(sections, start=1):
        if not should_continue():
            return None
        context = _section_context(sections, number, summary, written)
        script = model.write_script(title, section.text, tone, context)
        written.append(ScriptSection(section.title, script.text))
        usages.append(script.usage)
    return WrittenScript(written, total_usage(usages))


def _section_context(
    sections: list[Section],
    number: int,
    summary: str,
    written: list[ScriptSection],
) -> SectionContext | None:
    # A one-section document keeps the plain prompt, so its cost does not change.
    if len(sections) == 1:
        return None
    previous_titles = [section.title for section in written]
    so_far = continuity(summary, previous_titles, written[-1].script) if written else ""
    return SectionContext(sections[number - 1].title, number, len(sections), so_far)


def _record_analysis_failure(error: ModelError | ValueError) -> None:
    global last_error
    last_error = error.message if isinstance(error, ModelError) else str(error)
    log.warning("analysis_fell_back", error_type=type(error).__name__)
