import pytest

from phemius.errors import ModelError
from phemius.services import agent


class FailingModel:
    def complete(self, system: str, user: str, max_tokens: int) -> str:
        raise ModelError("OpenRouter returned 402.", hint="Add OpenRouter credits.")


@pytest.fixture
def failing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent, "_model_client", lambda: FailingModel())
    monkeypatch.setattr(agent, "last_error", None)


def test_heuristic_analyze_categorizes_a_how_to() -> None:
    analysis = agent.analyze("Deploy", "# Deploy\n\n1. Install the CLI.\n2. Run it.")

    assert analysis["category"] == "how-to / tutorial"
    assert analysis["suggested_tone"] == "teacher"


def test_heuristic_script_removes_markdown_and_code() -> None:
    text = (
        "# Setup\n\nRun `make` then see [the docs](https://example.com).\n\n```\nx\n```"
    )

    script = agent.make_script("Setup", text, "conversational")

    assert script.startswith("Alright, let's walk through Setup.")
    assert "Section: Setup." in script
    assert "https://" not in script
    assert "```" not in script and "`" not in script


@pytest.mark.usefixtures("failing_model")
def test_failing_model_raises_instead_of_using_offline_script() -> None:
    with pytest.raises(ModelError, match="402"):
        agent.make_script("Setup", "# Setup\n\nInstall it.", "neutral")


@pytest.mark.usefixtures("failing_model")
def test_failing_model_analysis_falls_back_and_records_error() -> None:
    analysis = agent.analyze("Deploy", "# Deploy\n\n1. Install the CLI.")

    assert analysis["category"] == "how-to / tutorial"
    assert agent.last_error == "OpenRouter returned 402."
