"""Split a long document into sections a script model rewrites one at a time.

A document that fits one request stays one section, so its prompt and cost do
not change. A longer one splits at its headings, then by size at paragraph,
sentence and word boundaries, and as a last resort mid-word, so no section is
over the limit however the document is written.
"""

import re
from dataclasses import dataclass

from phemius.models.prompts import SCRIPT_TEXT_LIMIT
from phemius.models.spoken_text import CODE_EXAMPLE_END

# A reply token is about four characters of English; budgeting three leaves room
# for a script that runs a little longer than its section.
CHARS_PER_REPLY_TOKEN = 3
# Without a floor, a tiny PHEMIUS_SCRIPT_MAX_TOKENS would turn one document into
# hundreds of paid calls; with it, the first section fails with the length hint.
MIN_SECTION_CHARS = 2000
CONTINUITY_LIMIT = 1500
SUMMARY_LIMIT = 300
TITLES_LIMIT = 400
TITLE_LIMIT = 80
TAIL_LIMIT = 500

HEADING = re.compile(r"^ {0,3}#{1,6}[ \t]+(?P<title>.*?)[ \t#]*$")
CODE_EXAMPLE_START = "[Code example"
# Coarsest first; each joiner puts back what its separator removed.
SIZE_LEVELS = [
    (re.compile(r"\n[ \t]*\n"), "\n\n"),
    (re.compile(r"(?<=[.!?])\s+"), " "),
    (re.compile(r"\s+"), " "),
]
type SizeLevel = tuple[re.Pattern[str], str]


@dataclass(frozen=True)
class Section:
    title: str
    text: str


def section_limit(script_max_tokens: int) -> int:
    """The most characters one section holds, leaving room for the reply."""
    reply_room = max(script_max_tokens * CHARS_PER_REPLY_TOKEN, MIN_SECTION_CHARS)
    return min(SCRIPT_TEXT_LIMIT - CONTINUITY_LIMIT, reply_room)


def split_sections(title: str, text: str, limit: int) -> list[Section]:
    """Sections of at most `limit` characters, in document order."""
    if len(text) <= limit:
        return [Section(title, text)]
    parts = [
        part
        for block in _heading_blocks(title, text)
        for part in _split_block(block, limit)
    ]
    return _pack(parts, limit)


def continuity(summary: str, previous_titles: list[str], previous_script: str) -> str:
    """What a later section's prompt says about the document so far, bounded.

    Built from what is already known rather than an extra model call per section.
    """
    parts = [
        f"The document: {summary.strip()[:SUMMARY_LIMIT]}" if summary.strip() else "",
        f"Sections covered so far: {_latest_titles(previous_titles)}.",
        f"The previous section's script ended: {_tail(previous_script)}",
    ]
    return "\n".join(part for part in parts if part)[:CONTINUITY_LIMIT]


def _heading_blocks(title: str, text: str) -> list[Section]:
    titles: list[str] = [title]
    bodies: list[list[str]] = [[]]
    is_in_code = False
    for line in text.splitlines():
        heading = None if is_in_code else HEADING.match(line)
        if heading is not None:
            titles.append(heading["title"][:TITLE_LIMIT] or title)
            bodies.append([])
        bodies[-1].append(line)
        is_in_code = line.startswith(CODE_EXAMPLE_START) or (
            is_in_code and line != CODE_EXAMPLE_END
        )
    blocks = [
        Section(name, "\n".join(body).strip()) for name, body in zip(titles, bodies)
    ]
    return [block for block in blocks if block.text]


def _pack(sections: list[Section], limit: int) -> list[Section]:
    """Merge neighbours that fit together, so many short headings cost few calls."""
    packed: list[Section] = []
    for section in sections:
        if packed and len(packed[-1].text) + 2 + len(section.text) <= limit:
            merged = f"{packed[-1].text}\n\n{section.text}"
            packed[-1] = Section(packed[-1].title, merged)
        else:
            packed.append(section)
    return packed


def _split_block(block: Section, limit: int) -> list[Section]:
    pieces = _split_by_size(block.text, limit, SIZE_LEVELS)
    return [
        Section(block.title if number == 1 else f"{block.title} (part {number})", piece)
        for number, piece in enumerate(pieces, start=1)
    ]


def _split_by_size(text: str, limit: int, levels: list[SizeLevel]) -> list[str]:
    if len(text) <= limit:
        return [text]
    if not levels:
        return [text[start : start + limit] for start in range(0, len(text), limit)]
    (separator, joiner), *finer = levels
    pieces = [
        part
        for piece in separator.split(text)
        if piece.strip()
        for part in _split_by_size(piece, limit, finer)
    ]
    return _join_up_to(pieces, joiner, limit)


def _join_up_to(pieces: list[str], joiner: str, limit: int) -> list[str]:
    chunks: list[str] = []
    for piece in pieces:
        if chunks and len(chunks[-1]) + len(joiner) + len(piece) <= limit:
            chunks[-1] += joiner + piece
        else:
            chunks.append(piece)
    return chunks


def _latest_titles(titles: list[str]) -> str:
    latest: list[str] = []
    length = 0
    for title in reversed(titles):
        clipped = title[:TITLE_LIMIT]
        length += len(clipped) + 2
        if latest and length > TITLES_LIMIT:
            break
        latest.insert(0, clipped)
    return "; ".join(latest)


def _tail(script: str) -> str:
    script = script.strip()
    if len(script) <= TAIL_LIMIT:
        return script
    clipped = script[-TAIL_LIMIT:]
    _cut_word, space, rest = clipped.partition(" ")
    return rest if space and rest else clipped
