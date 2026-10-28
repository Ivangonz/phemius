"""Tones, categories and prompts shared by every model, so providers behave alike."""

import json
import re
from collections.abc import Container
from typing import Any

from phemius.errors import ModelError
from phemius.models.base import Analysis, AudioSuitability, SuitabilitySource
from phemius.models.suitability import (
    Suitability,
    assess_suitability,
    rule_tone_rationale,
)

TONES = {
    "neutral": "Clear, calm and professional, like a good narrator reading a briefing.",
    "conversational": "Friendly and relaxed, like a colleague explaining this over "
    "coffee.",
    "podcast": "Engaging and energetic, like a tech podcast host walking through the "
    "topic.",
    "teacher": "Patient and structured, like a teacher: define terms, give a mini "
    "recap at the end.",
    "executive": "Concise and decision-oriented: lead with the point, skip the detail.",
}

# Which tone tends to suit which category (also the list of categories).
TONE_BY_CATEGORY = {
    "how-to / tutorial": "teacher",
    "reference / API": "neutral",
    "architecture / design": "conversational",
    "process / policy": "neutral",
    "meeting notes / status": "executive",
    "proposal / spec": "executive",
    "narrative / essay": "podcast",
    "other": "neutral",
}
CATEGORIES = list(TONE_BY_CATEGORY)
SUITABILITY_VERDICTS: tuple[AudioSuitability, ...] = (
    "recommended",
    "partial",
    "not_recommended",
)

SCRIPT_SYSTEM = """You turn written documentation into a script that will be read \
aloud by a text-to-speech voice.
Rules:
- Output plain spoken prose only. Never output markdown symbols (no asterisks, \
pound signs, backticks, pipes, brackets or bullet markers) and never output a URL; \
refer to a link by what it points to.
- Open with a one-sentence orientation ("This document covers ...").
- Code arrives as a "[Code example ...]" line, the code, then \
"[End of code example.]". Describe in words what the code does and why it matters. \
Never read code verbatim; say only a short command or identifier that matters.
- Tables arrive as a list of columns followed by "label: value" lines. Summarize \
them in sentences and point out what stands out rather than reading every cell.
- Turn lists into sentences, and spell out symbols a listener would stumble on.
- Say acronyms and file names the way a person would. Expand an acronym the \
first time it appears ("the CLI, the command-line interface"), then use the short \
form. Read "config.yaml" as "config dot yaml" and "README.md" as "the README".
- Use short sentences and signpost transitions ("First...", "Next...", "To wrap \
up...").
- Stay faithful to the source. Do not invent facts.
- Separate paragraphs with a blank line."""

ANALYSIS_SYSTEM = (
    "You classify documentation for an audio-listening app. Reply with JSON only."
)
# Room for two one-sentence explanations on top of the category and summary.
ANALYSIS_MAX_TOKENS = 500
ANALYSIS_TEXT_LIMIT = 6000
SCRIPT_TEXT_LIMIT = 40000


def analysis_prompt(title: str, text: str) -> str:
    return (
        f"Categories: {CATEGORIES}\nTones: {list(TONES)}\n\n"
        'Return {"category": one category, "summary": one sentence, '
        '"suggested_tone": best tone for listening to this document, '
        '"tone_rationale": one sentence on why that tone suits it, '
        '"audio_suitability": "recommended", "partial" or "not_recommended", '
        '"suitability_reason": one sentence on why}. A document that is mostly '
        "tables, code or lists of constants is not_recommended, because a "
        "listener cannot follow it by ear.\n\n"
        f"Title: {title}\n\nDocument (truncated):\n{text[:ANALYSIS_TEXT_LIMIT]}"
    )


def script_system(tone: str) -> str:
    return f"{SCRIPT_SYSTEM}\n\nTone: {tone} - {TONES.get(tone, TONES['neutral'])}"


def script_prompt(title: str, text: str) -> str:
    """The script request. Raises `ModelError` rather than trimming a long document."""
    if len(text) > SCRIPT_TEXT_LIMIT:
        raise ModelError(
            f"This document has {len(text):,} characters; one script covers up to"
            f" {SCRIPT_TEXT_LIMIT:,}.",
            hint="Split it into smaller documents for now; narrating long documents"
            " in chapters is planned.",
        )
    return f"Title: {title}\n\nDocument:\n{text}"


def parse_analysis(reply: str, text: str) -> Analysis:
    """Read the analysis JSON from a reply. Raises `ValueError` if there is none.

    A missing or unknown field falls back to the rules, judged on `text`; what the
    model wrote is kept whole.
    """
    data = _json_object(reply)
    category = _known(data.get("category"), TONE_BY_CATEGORY) or "other"
    tone, tone_rationale = _tone_and_rationale(data, category)
    suitability, source = _suitability(data, text)
    return Analysis(
        category=category,
        summary=str(data.get("summary", "")),
        suggested_tone=tone,
        tone_rationale=tone_rationale,
        audio_suitability=suitability.verdict,
        suitability_reason=suitability.reason,
        suitability_source=source,
    )


def _tone_and_rationale(data: dict[str, Any], category: str) -> tuple[str, str]:
    tone = _known(data.get("suggested_tone"), TONES)
    if tone is None:
        # Any rationale the model gave argued for a tone that is not used.
        tone = TONE_BY_CATEGORY[category]
        return tone, rule_tone_rationale(category, tone)
    rationale = _sentence(data.get("tone_rationale"))
    return tone, rationale or rule_tone_rationale(category, tone)


def _suitability(
    data: dict[str, Any], text: str
) -> tuple[Suitability, SuitabilitySource]:
    verdict = _verdict(data.get("audio_suitability"))
    reason = _sentence(data.get("suitability_reason"))
    if verdict is None or reason is None:
        return assess_suitability(text), "heuristic"
    return Suitability(verdict, reason), "model"


def _verdict(value: object) -> AudioSuitability | None:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[\s-]+", "_", value.strip().lower())
    return next((item for item in SUITABILITY_VERDICTS if item == normalized), None)


def _known(value: object, options: Container[str]) -> str | None:
    return value if isinstance(value, str) and value in options else None


def _sentence(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _json_object(reply: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", reply, re.S)
    data = json.loads(match.group(0)) if match else None
    if not isinstance(data, dict):
        raise ValueError("Model reply contained no JSON object")
    return data
