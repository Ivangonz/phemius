import pytest

from phemius.models.prompts import parse_analysis


def test_unknown_category_and_tone_fall_back_to_other() -> None:
    reply = '{"category": "poetry", "summary": "A poem.", "suggested_tone": "shouty"}'

    analysis = parse_analysis(reply)

    assert analysis["category"] == "other"
    assert analysis["suggested_tone"] == "neutral"


@pytest.mark.parametrize("reply", ["No JSON here.", "[1, 2]", '{"category": '])
def test_reply_without_a_json_object_raises(reply: str) -> None:
    with pytest.raises(ValueError):
        parse_analysis(reply)
