import pytest

from phemius.errors import ModelError
from phemius.models.prompts import (
    SCRIPT_TEXT_LIMIT,
    parse_analysis,
    script_prompt,
    script_system,
)
from phemius.models.spoken_text import CODE_EXAMPLE_END, to_spoken_text


def test_unknown_category_and_tone_fall_back_to_other() -> None:
    reply = '{"category": "poetry", "summary": "A poem.", "suggested_tone": "shouty"}'

    analysis = parse_analysis(reply)

    assert analysis["category"] == "other"
    assert analysis["suggested_tone"] == "neutral"


@pytest.mark.parametrize("reply", ["No JSON here.", "[1, 2]", '{"category": '])
def test_reply_without_a_json_object_raises(reply: str) -> None:
    with pytest.raises(ValueError):
        parse_analysis(reply)


def test_script_prompt_rejects_a_document_over_the_limit() -> None:
    with pytest.raises(ModelError, match="characters") as raised:
        script_prompt("Long", "x" * (SCRIPT_TEXT_LIMIT + 1))

    assert raised.value.hint


def test_script_prompt_keeps_the_whole_document() -> None:
    text = "x" * SCRIPT_TEXT_LIMIT

    assert script_prompt("Fits", text).endswith(text)


def test_script_system_explains_the_code_example_markers() -> None:
    marked = to_spoken_text("```\nmake run\n```")
    header = marked.splitlines()[0]

    system = script_system("neutral")

    assert header.startswith("[Code example") and "[Code example" in system
    assert CODE_EXAMPLE_END in system
