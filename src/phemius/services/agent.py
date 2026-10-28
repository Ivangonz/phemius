"""Categorizes documents and rewrites them as listening-friendly scripts.

Uses OpenRouter when OPENROUTER_API_KEY is set; otherwise falls back to heuristics
so the pipeline still runs end to end offline. A failed model call also falls back,
and the error is kept in `last_error` so the UI can show it.
"""

import json
import re
from typing import TypedDict

import structlog

from phemius.config import load_config
from phemius.models.openrouter import OpenRouterClient, get_client

log = structlog.get_logger(__name__)

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

# Heuristic category rules, checked in order.
CATEGORY_PATTERNS = [
    ("how-to / tutorial", r"\bstep \d|^\s*\d+\.\s|how to|install|getting started"),
    ("reference / API", r"\bendpoint|parameter|returns?\b|\bapi\b|\bargs?\b"),
    ("architecture / design", r"architecture|component|diagram|design"),
    ("process / policy", r"\bpolicy|\bprocedure|must|compliance"),
    ("meeting notes / status", r"attendees|action items|standup|status"),
    ("proposal / spec", r"proposal|requirements|goals|non-goals|rfc"),
]

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

ANALYSIS_TEXT_LIMIT = 6000
SCRIPT_TEXT_LIMIT = 40000

# Most recent model failure, shown in the UI so a bad key or model is not silent.
last_error: str | None = None


class DocumentAnalysis(TypedDict):
    category: str
    summary: str
    suggested_tone: str


def _model_client() -> OpenRouterClient | None:
    config = load_config()
    if not config.openrouter_api_key:
        return None
    return get_client(config.openrouter_api_key, config.model)


def _record_failure(error: Exception) -> None:
    global last_error
    last_error = f"{type(error).__name__}: {error}"[:300]
    log.warning("model_call_failed", error_type=type(error).__name__)


def analyze(title: str, text: str) -> DocumentAnalysis:
    client = _model_client()
    if client:
        try:
            return _analyze_with_model(client, title, text)
        except Exception as error:  # fall back to heuristics and surface the error
            _record_failure(error)
    return heuristic_analyze(text)


def _analyze_with_model(
    client: OpenRouterClient, title: str, text: str
) -> DocumentAnalysis:
    output = client.complete(
        "You classify documentation for an audio-listening app. Reply with JSON only.",
        f"Categories: {CATEGORIES}\nTones: {list(TONES)}\n\n"
        'Return {"category": one category, "summary": one sentence, '
        '"suggested_tone": best tone for listening to this document}.\n\n'
        f"Title: {title}\n\nDocument (truncated):\n{text[:ANALYSIS_TEXT_LIMIT]}",
        max_tokens=300,
    )
    match = re.search(r"\{.*\}", output, re.S)
    if not match:
        raise ValueError("Model reply contained no JSON object")
    data = json.loads(match.group(0))
    category = data.get("category") if data.get("category") in CATEGORIES else "other"
    tone = data.get("suggested_tone")
    return DocumentAnalysis(
        category=category,
        summary=str(data.get("summary", "")),
        suggested_tone=tone if tone in TONES else TONE_BY_CATEGORY[category],
    )


def heuristic_analyze(text: str) -> DocumentAnalysis:
    lowered = text.lower()
    category = next(
        (
            name
            for name, pattern in CATEGORY_PATTERNS
            if re.search(pattern, lowered, re.M)
        ),
        "other",
    )
    plain = re.sub(r"[#*`>]", "", text).strip()
    first_sentence = re.split(r"(?<=[.!?])\s", plain, maxsplit=1)[0]
    return DocumentAnalysis(
        category=category,
        summary=first_sentence[:200],
        suggested_tone=TONE_BY_CATEGORY[category],
    )


def make_script(title: str, text: str, tone: str) -> str:
    client = _model_client()
    if client:
        try:
            return _script_with_model(client, title, text, tone)
        except Exception as error:  # fall back to heuristics and surface the error
            _record_failure(error)
    return heuristic_script(title, text, tone)


def _script_with_model(
    client: OpenRouterClient, title: str, text: str, tone: str
) -> str:
    tone_description = TONES.get(tone, TONES["neutral"])
    return client.complete(
        f"{SCRIPT_SYSTEM}\n\nTone: {tone} - {tone_description}",
        f"Title: {title}\n\nDocument:\n{text[:SCRIPT_TEXT_LIMIT]}",
        max_tokens=load_config().script_max_tokens,
    ).strip()


def heuristic_script(title: str, text: str, tone: str) -> str:
    """Offline fallback: strip markdown and make code and lists speakable."""
    intro = {
        "conversational": f"Alright, let's walk through {title}.",
        "podcast": f"Welcome back! Today we're digging into {title}.",
        "teacher": f"In this lesson, we'll cover {title}.",
        "executive": f"Here's the brief on {title}.",
    }.get(tone, f"This document is titled {title}.")
    return f"{intro}\n\n{_strip_markdown(text)}"


def _strip_markdown(text: str) -> str:
    text = re.sub(
        r"```.*?```",
        " (a code example appears here in the written version.) ",
        text,
        flags=re.S,
    )
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*(.+)$", r"Section: \1.", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*(\d+)\.\s+", r"Step \1. ", text, flags=re.M)
    text = re.sub(r"[*_]{1,3}", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
