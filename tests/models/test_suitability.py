from pathlib import Path

from phemius.models.suitability import assess_suitability

FIXTURES = Path(__file__).parents[1] / "fixtures"
SAMPLES = Path(__file__).parents[2] / "samples"


def test_table_heavy_reference_is_not_recommended_with_a_reason() -> None:
    text = (FIXTURES / "suitability" / "error-codes-reference.md").read_text()

    suitability = assess_suitability(text)

    assert suitability.verdict == "not_recommended"
    assert "table" in suitability.reason


def test_prose_guide_is_recommended() -> None:
    suitability = assess_suitability((SAMPLES / "deploy-guide.md").read_text())

    assert suitability.verdict == "recommended"


def test_document_that_is_mostly_code_is_not_recommended() -> None:
    code = "\n".join(f"step_{number} = run({number})" for number in range(30))
    text = f"# Script\n\nThe deploy script.\n\n```python\n{code}\n```"

    suitability = assess_suitability(text)

    assert suitability.verdict == "not_recommended"
    assert "code" in suitability.reason


def test_list_of_constants_is_not_recommended() -> None:
    constants = "\n".join(f"MAX_RETRIES_{number} = {number}" for number in range(12))

    suitability = assess_suitability(f"# Constants\n\n{constants}")

    assert suitability.verdict == "not_recommended"
    assert "constants" in suitability.reason


def test_prose_with_one_table_is_partial() -> None:
    prose = " ".join(["Deploys roll out in waves to limit the blast radius."] * 4)
    rows = "\n".join(f"| {wave} | {wave * 15}% |" for wave in range(1, 7))
    text = f"# Rollout\n\n{prose}\n\n| Wave | Share |\n| --- | --- |\n{rows}"

    suitability = assess_suitability(text)

    assert suitability.verdict == "partial"
    assert "table" in suitability.reason


def test_very_short_document_is_partial() -> None:
    suitability = assess_suitability("# Guide\n\nInstall with pip.")

    assert suitability.verdict == "partial"
    assert "short" in suitability.reason
