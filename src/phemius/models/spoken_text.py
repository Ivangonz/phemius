"""Prepare a document's text for a script model, whichever provider writes it.

Code blocks become marked code examples the prompt tells the model to describe,
tables become "label: value" lines, links keep only their text, and URLs and
images are dropped. Code inside a code example is kept verbatim so the model can
say what it does.
"""

import re
from collections.abc import Callable

CODE_EXAMPLE_END = "[End of code example.]"
CODE_EXAMPLE = re.compile(
    r"^\[Code example\b[^\n]*\]\n.*?^" + re.escape(CODE_EXAMPLE_END) + "$",
    re.M | re.S,
)

FENCED_CODE = re.compile(
    r"^[ \t]{0,3}(?P<fence>`{3,}|~{3,})[ \t]*(?P<language>[\w+#.-]*)[^\n]*\n"
    r"(?P<code>.*?)(?:^[ \t]{0,3}(?P=fence)[ \t]*$|\Z)",
    re.M | re.S,
)
# A run of lines indented by four spaces or a tab, after a blank line.
INDENTED_CODE = re.compile(r"(?:\A|(?<=\n\n))(?:(?: {4}|\t)[^\n]*(?:\n|\Z))+")
LIST_ITEM = re.compile(r"\s*(?:[-*+]|\d+[.)])\s")

TABLE_SEPARATOR = r"[ \t]*\|?(?:[ \t]*:?-+:?[ \t]*\|)+(?:[ \t]*:?-+:?[ \t]*)?"
TABLE = re.compile(
    rf"^(?P<header>[^\n]*\|[^\n]*)\n{TABLE_SEPARATOR}$\n?"
    r"(?P<rows>(?:^[^\n]*\|[^\n]*(?:\n|\Z))*)",
    re.M,
)

IMAGE = re.compile(r"!\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])")
INLINE_LINK = re.compile(r"\[([^\]]+)\]\((?:[^()\s]|\([^)]*\))*(?:\s+\"[^\"]*\")?\)")
REFERENCE_LINK = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
LINK_DEFINITION = re.compile(r"^[ \t]{0,3}\[[^\]]+\]:[ \t]*\S+[^\n]*\n?", re.M)
URL = r"<?(?:https?://|www\.)[^\s<>]*[^\s<>.,;:!?'\")\]]>?"
# A URL with the spaces that would be left dangling once it is gone.
URL_WITH_SPACING = re.compile(rf"^[ \t]*{URL}[ \t]*|[ \t]*{URL}", re.M)


def to_spoken_text(text: str) -> str:
    """Return `text` with code marked, tables flattened and URLs removed."""
    return _map_code(text, FENCED_CODE, _fenced_example, _prose_or_indented).strip()


def _prose_or_indented(text: str) -> str:
    return _map_code(text, INDENTED_CODE, _indented_example, _prose)


def _map_code(
    text: str,
    code: re.Pattern[str],
    on_code: Callable[[re.Match[str]], str],
    on_prose: Callable[[str], str],
) -> str:
    """Apply `on_code` to each match of `code` and `on_prose` to the text between."""
    parts: list[str] = []
    position = 0
    for match in code.finditer(text):
        parts += [on_prose(text[position : match.start()]), on_code(match)]
        position = match.end()
    return "".join([*parts, on_prose(text[position:])])


def _prose(text: str) -> str:
    text = TABLE.sub(_flatten_table, text)
    text = IMAGE.sub("", text)
    text = LINK_DEFINITION.sub("", text)
    text = INLINE_LINK.sub(r"\1", text)
    text = REFERENCE_LINK.sub(r"\1", text)
    return _tidy_spaces(URL_WITH_SPACING.sub("", text))


def _tidy_spaces(text: str) -> str:
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\([ \t]+", "(", text)
    text = re.sub(r"(?<=\S)[ \t]+(?=[.,;:!?])", "", text)
    text = re.sub(r"(?<=\S)[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+$", "", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text)


def _fenced_example(match: re.Match[str]) -> str:
    return _code_example(match["code"], match["language"])


def _indented_example(match: re.Match[str]) -> str:
    block = match.group(0)
    line_before = match.string[: match.start()].rstrip().rpartition("\n")[2]
    if LIST_ITEM.match(block) or LIST_ITEM.match(line_before):
        return _prose(block)
    code = re.sub(r"^(?: {4}|\t)", "", block, flags=re.M)
    return _code_example(code) + "\n"


def _code_example(code: str, language: str = "") -> str:
    lines = code.rstrip("\n").splitlines()
    if not lines:
        return ""
    plural = "s" if len(lines) > 1 else ""
    language_part = f" in {language}" if language else ""
    header = (
        f"[Code example{language_part}, {len(lines)} line{plural}."
        " Describe it in words; do not read it out.]"
    )
    return "\n".join([header, *lines, CODE_EXAMPLE_END])


def _flatten_table(match: re.Match[str]) -> str:
    headers = _cells(match["header"])
    rows = [_cells(row) for row in match["rows"].splitlines() if row.strip()]
    lines = [f"A table with columns {_join_words(headers)}."]
    lines += [_row_sentence(headers, row) for row in rows]
    return "\n".join(lines) + "\n"


def _row_sentence(headers: list[str], row: list[str]) -> str:
    pairs = [
        f"{label}: {value}" if label else value
        for label, value in zip(headers, row, strict=False)
        if value
    ]
    return "; ".join(pairs) + "."


def _cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _join_words(words: list[str]) -> str:
    named = [word for word in words if word]
    if len(named) < 2:
        return "".join(named)
    return f"{', '.join(named[:-1])} and {named[-1]}"
