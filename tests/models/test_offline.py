from pathlib import Path

from phemius.models.base import SectionContext
from phemius.models.offline import OfflineModel

FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_analyze_categorizes_a_how_to() -> None:
    analysis = OfflineModel().analyze(
        "Deploy", "# Deploy\n\n1. Install the CLI.\n2. Run it."
    )

    assert analysis["category"] == "how-to / tutorial"
    assert analysis["suggested_tone"] == "teacher"


def test_write_script_removes_markdown_and_code() -> None:
    text = (
        "# Setup\n\nRun `make` then see [the docs](https://example.com).\n\n```\nx\n```"
    )

    script = OfflineModel().write_script("Setup", text, "conversational").text

    assert script.startswith("Alright, let's walk through Setup.")
    assert "Section: Setup." in script
    assert "https://" not in script
    assert "```" not in script and "`" not in script


def test_a_later_section_does_not_introduce_the_document_again() -> None:
    section = SectionContext("Usage", 2, 2, "")

    script = OfflineModel().write_script("Guide", "Run it.", "podcast", section)

    assert script.text == "Run it."


def test_offline_script_is_local_so_it_costs_nothing() -> None:
    script = OfflineModel().write_script("Setup", "Install it.", "neutral")

    assert script.usage.is_local


def test_summary_skips_the_title_heading() -> None:
    text = "# Deploying the Billing Service\n\nThis guide explains it.\nMore here."

    analysis = OfflineModel().analyze("Deploying the Billing Service", text)

    assert analysis["summary"] == "This guide explains it."


def test_analyze_flags_its_suitability_and_rationale_as_heuristic() -> None:
    text = (FIXTURES / "suitability" / "error-codes-reference.md").read_text()

    analysis = OfflineModel().analyze("Error codes", text)

    assert analysis["audio_suitability"] == "not_recommended"
    assert analysis["suitability_reason"]
    assert analysis["suggested_tone"] in analysis["tone_rationale"]
    assert analysis["suitability_source"] == "heuristic"
