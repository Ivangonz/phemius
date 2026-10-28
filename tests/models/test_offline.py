from phemius.models.offline import OfflineModel


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

    script = OfflineModel().write_script("Setup", text, "conversational")

    assert script.startswith("Alright, let's walk through Setup.")
    assert "Section: Setup." in script
    assert "https://" not in script
    assert "```" not in script and "`" not in script


def test_summary_skips_the_title_heading() -> None:
    text = "# Deploying the Billing Service\n\nThis guide explains it.\nMore here."

    analysis = OfflineModel().analyze("Deploying the Billing Service", text)

    assert analysis["summary"] == "This guide explains it."
