"""Tones, categories and prompts shared by every model, so providers behave alike."""

import json
import re
from typing import Any

from phemius.errors import ModelError
from phemius.models.base import Analysis

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
ANALYSIS_MAX_TOKENS = 300
ANALYSIS_TEXT_LIMIT = 6000
SCRIPT_TEXT_LIMIT = 40000


def analysis_prompt(title: str, text: str) -> str:
    return (
        f"Categories: {CATEGORIES}\nTones: {list(TONES)}\n\n"
        'Return {"category": one category, "summary": one sentence, '
        '"suggested_tone": best tone for listening to this document}.\n\n'
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


def parse_analysis(reply: str) -> Analysis:
    """Read the analysis JSON from a reply. Raises `ValueError` if there is none."""
    data = _json_object(reply)
    category = data.get("category")
    if category not in TONE_BY_CATEGORY:
        category = "other"
    tone = data.get("suggested_tone")
    return Analysis(
        category=category,
        summary=str(data.get("summary", "")),
        suggested_tone=tone if tone in TONES else TONE_BY_CATEGORY[category],
    )


def _json_object(reply: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", reply, re.S)
    data = json.loads(match.group(0)) if match else None
    if not isinstance(data, dict):
        raise ValueError("Model reply contained no JSON object")
    return data
