import pytest

from phemius.errors import ModelError
from phemius.services import agent
from tests.models.fakes import (
    FailingScriptModel,
    RecordingScriptModel,
    UseScriptModel,
)


@pytest.fixture
def failing_model(
    use_script_model: UseScriptModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_script_model(FailingScriptModel())
    monkeypatch.setattr(agent, "last_error", None)


def test_no_model_configured_writes_offline_script() -> None:
    script = agent.make_script("Setup", "# Setup\n\nInstall it.", "executive").text

    assert script.startswith("Here's the brief on Setup.")


def test_model_receives_text_with_code_and_urls_made_speakable(
    use_script_model: UseScriptModel,
) -> None:
    model = RecordingScriptModel()
    use_script_model(model)
    text = "Read [the guide](https://example.com).\n\n```sh\nmake run\n```"

    agent.make_script("Setup", text, "neutral")

    [sent] = model.script_texts
    assert "https://" not in sent and "```" not in sent
    assert sent.startswith("Read the guide.\n\n[Code example in sh, 1 line.")


def test_offline_script_says_a_code_example_instead_of_reading_it() -> None:
    script = agent.make_script("Setup", "Run:\n\n    make run\n", "neutral").text

    assert "make run" not in script
    assert "code example" in script


@pytest.mark.usefixtures("failing_model")
def test_failing_model_raises_instead_of_using_offline_script() -> None:
    with pytest.raises(ModelError, match="402"):
        agent.make_script("Setup", "# Setup\n\nInstall it.", "neutral")


@pytest.mark.usefixtures("failing_model")
def test_failing_model_analysis_falls_back_and_records_error() -> None:
    analysis = agent.analyze("Deploy", "# Deploy\n\n1. Install the CLI.")

    assert analysis["category"] == "how-to / tutorial"
    assert analysis["suitability_source"] == "heuristic"
    assert analysis["suitability_reason"]
    assert agent.last_error == "Provider returned 402."


def test_unknown_provider_fails_the_script_with_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", "mystery")

    with pytest.raises(ModelError) as raised:
        agent.make_script("Setup", "# Setup", "neutral")

    assert raised.value.hint is not None
