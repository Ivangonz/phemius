"""Offline rules that categorize and script documents without any model.

Selected when no script model is configured, so the pipeline runs end to end with
no network and no keys.
"""

import re

from phemius.config import Config
from phemius.models.base import Analysis, Script, ScriptModelCheck, TokenUsage
from phemius.models.prompts import TONE_BY_CATEGORY
from phemius.models.spoken_text import CODE_EXAMPLE
from phemius.models.suitability import assess_suitability, rule_tone_rationale

# Category rules, checked in order.
CATEGORY_PATTERNS = [
    ("how-to / tutorial", r"\bstep \d|^\s*\d+\.\s|how to|install|getting started"),
    ("reference / API", r"\bendpoint|parameter|returns?\b|\bapi\b|\bargs?\b"),
    ("architecture / design", r"architecture|component|diagram|design"),
    ("process / policy", r"\bpolicy|\bprocedure|must|compliance"),
    ("meeting notes / status", r"attendees|action items|standup|status"),
    ("proposal / spec", r"proposal|requirements|goals|non-goals|rfc"),
]

CODE_MENTION = " (a code example appears here in the written version.) "


class OfflineModel:
    model = "offline rules"

    def analyze(self, title: str, text: str) -> Analysis:
        category = _match_category(text.lower())
        tone = TONE_BY_CATEGORY[category]
        suitability = assess_suitability(text)
        return Analysis(
            category=category,
            summary=_first_sentence(text)[:200],
            suggested_tone=tone,
            tone_rationale=rule_tone_rationale(category, tone),
            audio_suitability=suitability.verdict,
            suitability_reason=suitability.reason,
            suitability_source="heuristic",
        )

    def write_script(self, title: str, text: str, tone: str) -> Script:
        """Strip markdown and make code and lists speakable."""
        intro = {
            "conversational": f"Alright, let's walk through {title}.",
            "podcast": f"Welcome back! Today we're digging into {title}.",
            "teacher": f"In this lesson, we'll cover {title}.",
            "executive": f"Here's the brief on {title}.",
        }.get(tone, f"This document is titled {title}.")
        return Script(f"{intro}\n\n{_strip_markdown(text)}", TokenUsage(is_local=True))

    def check(self) -> ScriptModelCheck:
        return ScriptModelCheck(is_reachable=True, model=self.model, latency_ms=0.0)


def from_config(config: Config) -> OfflineModel:
    return OfflineModel()


def _first_sentence(text: str) -> str:
    """The first sentence of the body, skipping headings such as the title."""
    body = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    plain = " ".join(re.sub(r"[*`>]", "", body).split())
    return re.split(r"(?<=[.!?])\s", plain, maxsplit=1)[0]


def _match_category(lowered: str) -> str:
    return next(
        (
            name
            for name, pattern in CATEGORY_PATTERNS
            if re.search(pattern, lowered, re.M)
        ),
        "other",
    )


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", CODE_MENTION, text, flags=re.S)
    text = CODE_EXAMPLE.sub(CODE_MENTION, text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*(.+)$", r"Section: \1.", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*(\d+)\.\s+", r"Step \1. ", text, flags=re.M)
    text = re.sub(r"[*_]{1,3}", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
