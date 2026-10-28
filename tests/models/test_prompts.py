import json

import pytest

from phemius.errors import ModelError
from phemius.models.prompts import (
    SCRIPT_TEXT_LIMIT,
    analysis_prompt,
    parse_analysis,
    script_prompt,
    script_system,
)
from phemius.models.spoken_text import CODE_EXAMPLE_END, to_spoken_text


def test_unknown_category_and_tone_fall_back_to_other() -> None:
    reply = '{"category": "poetry", "summary": "A poem.", "suggested_tone": "shouty"}'

    analysis = parse_analysis(reply, PROSE)

    assert analysis["category"] == "other"
    assert analysis["suggested_tone"] == "neutral"


PROSE = " ".join(["Deploys roll out in waves to limit the blast radius."] * 6)
TABLE = "| Code | Status |\n| --- | --- |\n" + "\n".join(
    f"| error_{number} | 4{number:02} |" for number in range(20)
)


def test_analysis_prompt_asks_for_suitability_and_tone_rationale() -> None:
    prompt = analysis_prompt("Guide", PROSE)

    for field in ["audio_suitability", "suitability_reason", "tone_rationale"]:
        assert field in prompt
    assert "not_recommended" in prompt


def test_model_suitability_and_rationale_are_kept_in_full() -> None:
    reason = " ".join(["Mostly a table of error codes."] * 20)
    reply = json.dumps(
        {
            "category": "reference / API",
            "summary": "Lists error codes.",
            "suggested_tone": "neutral",
            "tone_rationale": "A calm voice suits a list of codes.",
            "audio_suitability": "not_recommended",
            "suitability_reason": reason,
        }
    )

    analysis = parse_analysis(reply, PROSE)

    assert analysis["audio_suitability"] == "not_recommended"
    assert analysis["suitability_reason"] == reason
    assert analysis["tone_rationale"] == "A calm voice suits a list of codes."
    assert analysis["suitability_source"] == "model"


def test_suitability_spelled_with_spaces_is_understood() -> None:
    reply = json.dumps(
        {"audio_suitability": "Not recommended", "suitability_reason": "Tables."}
    )

    analysis = parse_analysis(reply, PROSE)

    assert analysis["audio_suitability"] == "not_recommended"
    assert analysis["suitability_source"] == "model"


@pytest.mark.parametrize("suitability", ["maybe", None, 3, ["partial"]])
def test_unknown_suitability_falls_back_to_the_rules(suitability: object) -> None:
    reply = json.dumps({"category": ["reference"], "audio_suitability": suitability})

    analysis = parse_analysis(reply, TABLE)

    assert analysis["audio_suitability"] == "not_recommended"
    assert "table" in analysis["suitability_reason"]
    assert analysis["suitability_source"] == "heuristic"


def test_missing_tone_rationale_is_explained_by_the_rules() -> None:
    reply = '{"category": "how-to / tutorial", "suggested_tone": "teacher"}'

    analysis = parse_analysis(reply, PROSE)

    assert "teacher" in analysis["tone_rationale"]
    assert "how-to" in analysis["tone_rationale"]


@pytest.mark.parametrize("reply", ["No JSON here.", "[1, 2]", '{"category": '])
def test_reply_without_a_json_object_raises(reply: str) -> None:
    with pytest.raises(ValueError):
        parse_analysis(reply, PROSE)


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
