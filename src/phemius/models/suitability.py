"""Rules that judge whether a document works as audio, without any model.

Used by the offline provider and whenever a model gives no usable verdict. A
document is measured by the share of its characters in tables, code and
key/value constants, which a listener cannot follow by ear.
"""

import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from phemius.models.base import AudioSuitability

type LineKind = Literal["prose", "tables", "code", "lists of constants"]

NOT_RECOMMENDED_SHARE = 0.5
PARTIAL_SHARE = 0.25
# Under about 15 seconds of speech: worth reading, hardly worth a listen.
SHORT_WORD_COUNT = 40

FENCE = re.compile(r"^[ \t]{0,3}(?:`{3,}|~{3,})")
INDENTED_CODE = re.compile(r"^(?: {4}|\t)(?!\s*(?:[-*+]|\d+[.)])\s)")
# `NAME = value` or `key: value`, where the value is a few words at most.
CONSTANT = re.compile(
    r"^\s*(?:[-*+]\s+)?`?[A-Za-z_][\w.-]*`?\s*[:=]\s*\S+(?:\s+\S+){0,2}\s*$"
)


@dataclass(frozen=True)
class Suitability:
    verdict: AudioSuitability
    reason: str


def assess_suitability(text: str) -> Suitability:
    characters = Counter[LineKind]()
    for kind, line in _classified_lines(text):
        characters[kind] += len(line.strip())
    total = sum(characters.values()) or 1
    structured = {
        kind: count for kind, count in characters.most_common() if kind != "prose"
    }
    share = sum(structured.values()) / total
    kinds = " and ".join(structured)
    if share >= NOT_RECOMMENDED_SHARE:
        return Suitability(
            "not_recommended",
            f"About {share:.0%} of it is {kinds}, which listeners cannot follow"
            " by ear.",
        )
    if len(text.split()) < SHORT_WORD_COUNT:
        return Suitability(
            "partial", "It is very short, so the audio would last only seconds."
        )
    if share >= PARTIAL_SHARE:
        return Suitability(
            "partial",
            f"About {share:.0%} of it is {kinds}; the audio can only summarize"
            " those parts.",
        )
    return Suitability("recommended", "It is mostly prose, which reads well aloud.")


def rule_tone_rationale(category: str, tone: str) -> str:
    return f"It reads as a {category} document, which usually suits the {tone} tone."


def _classified_lines(text: str) -> Iterator[tuple[LineKind, str]]:
    is_in_fence = False
    for line in text.splitlines():
        if not line.strip():
            continue
        if FENCE.match(line):
            is_in_fence = not is_in_fence
            yield "code", line
        elif is_in_fence or INDENTED_CODE.match(line):
            yield "code", line
        else:
            yield _prose_line_kind(line), line


def _prose_line_kind(line: str) -> LineKind:
    if line.count("|") >= 2:
        return "tables"
    if CONSTANT.match(line):
        return "lists of constants"
    return "prose"
