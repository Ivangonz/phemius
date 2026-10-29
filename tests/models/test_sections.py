import pytest

from phemius.models.prompts import SCRIPT_TEXT_LIMIT
from phemius.models.sections import (
    CONTINUITY_LIMIT,
    MIN_SECTION_CHARS,
    TITLE_LIMIT,
    continuity,
    section_limit,
    split_sections,
)
from phemius.models.spoken_text import to_spoken_text

LIMIT = 300
PARAGRAPH = "Deploys roll out in waves. Each wave waits for the last one to settle."


def _heading_document(headings: list[str], paragraphs_each: int) -> str:
    body = "\n\n".join([PARAGRAPH] * paragraphs_each)
    return "\n\n".join(f"## {heading}\n\n{body}" for heading in headings)


def _words(text: str) -> list[str]:
    return text.split()


def test_a_short_document_stays_one_section_with_its_title() -> None:
    text = _heading_document(["Setup", "Usage"], 1)

    [section] = split_sections("Guide", text, len(text))

    assert (section.title, section.text) == ("Guide", text)


def test_a_long_document_is_split_at_its_headings_in_order() -> None:
    intro = f"{PARAGRAPH} {PARAGRAPH}\n\n"
    text = intro + _heading_document(["Setup", "Usage", "Upgrades"], 3)

    sections = split_sections("Guide", text, LIMIT)

    assert [section.title for section in sections] == [
        "Guide",
        "Setup",
        "Usage",
        "Upgrades",
    ]
    assert all(len(section.text) <= LIMIT for section in sections)
    assert _words(" ".join(section.text for section in sections)) == _words(text)


def test_small_neighbouring_headings_share_a_section() -> None:
    text = _heading_document(["One", "Two", "Three", "Four"], 1)

    sections = split_sections("Guide", text, len(text) // 2 + 10)

    assert [section.title for section in sections] == ["One", "Three"]


def test_an_oversized_block_without_headings_splits_at_paragraphs() -> None:
    text = "\n\n".join([PARAGRAPH] * 12)

    sections = split_sections("Notes", text, LIMIT)

    assert len(sections) > 1
    assert [section.title for section in sections[:2]] == ["Notes", "Notes (part 2)"]
    assert all(len(section.text) <= LIMIT for section in sections)
    assert all(section.text.endswith("settle.") for section in sections)


def test_an_oversized_paragraph_splits_at_sentences() -> None:
    text = " ".join([PARAGRAPH] * 12)

    sections = split_sections("Notes", text, LIMIT)

    assert all(len(section.text) <= LIMIT for section in sections)
    assert all(section.text.endswith(".") for section in sections)
    assert _words(" ".join(section.text for section in sections)) == _words(text)


def test_one_enormous_line_with_no_breaks_is_still_split_under_the_limit() -> None:
    text = "x" * (LIMIT * 10 + 7)

    sections = split_sections("Dump", text, LIMIT)

    assert all(0 < len(section.text) <= LIMIT for section in sections)
    assert "".join(section.text for section in sections) == text


def test_an_enormous_heading_is_clipped_to_a_short_title() -> None:
    text = "# " + "h" * (LIMIT * 5) + "\n\n" + PARAGRAPH

    sections = split_sections("Dump", text, LIMIT)

    assert all(len(section.text) <= LIMIT for section in sections)
    assert all(len(section.title) <= TITLE_LIMIT + 10 for section in sections)


def test_a_comment_inside_a_code_example_is_not_a_heading() -> None:
    code = "```python\n# not a heading\nprint('hi')\n```"
    text = to_spoken_text(f"## Setup\n\n{PARAGRAPH}\n\n{code}\n\n" + PARAGRAPH * 4)

    sections = split_sections("Guide", text, LIMIT)

    assert "not a heading" not in [section.title for section in sections]


def test_section_limit_leaves_room_for_the_reply_and_the_continuity() -> None:
    assert section_limit(1_000_000) == SCRIPT_TEXT_LIMIT - CONTINUITY_LIMIT
    assert section_limit(4000) < section_limit(8000) < SCRIPT_TEXT_LIMIT
    assert section_limit(1) == MIN_SECTION_CHARS


def test_continuity_keeps_the_latest_titles_and_the_previous_ending() -> None:
    summary = "Explains how deploys roll out."

    text = continuity(summary, ["Setup", "Usage"], "First. Then we deploy it.")

    assert summary in text
    assert "Setup" in text and "Usage" in text
    assert text.endswith("Then we deploy it.")


@pytest.mark.parametrize("title_count", [1, 5000])
def test_continuity_stays_bounded_however_long_the_document(title_count: int) -> None:
    titles = [f"Section {number} " + "t" * 200 for number in range(title_count)]

    text = continuity("s" * 10_000, titles, "word " * 10_000)

    assert len(text) <= CONTINUITY_LIMIT
    assert titles[-1][:20] in text
