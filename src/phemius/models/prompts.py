"""Tones, categories and prompts shared by every model, so providers behave alike."""

import json
import re
from typing import Any

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
- Output plain spoken prose only: no markdown, no bullet symbols, no headings syntax, \
no URLs read character by character.
- Open with a one-sentence orientation ("This document covers ...").
- Convert code blocks, tables and lists into natural spoken descriptions. Never read \
code verbatim; say what it does, and spell out only short commands/identifiers that \
matter.
- Spell out symbols and abbreviations a listener would stumble on.
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
    return f"Title: {title}\n\nDocument:\n{text[:SCRIPT_TEXT_LIMIT]}"


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
