import pytest

from phemius.errors import ModelError
from phemius.models.prompts import SCRIPT_TEXT_LIMIT, parse_analysis, script_prompt


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
