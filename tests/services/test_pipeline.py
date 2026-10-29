from pathlib import Path

import pytest

from phemius.errors import ModelError
from phemius.models.base import Script, SectionContext, TokenUsage
from phemius.services import pipeline, queue, runner
from phemius.store import audio as audio_store
from phemius.store import database
from phemius.store import documents as document_store
from phemius.store import jobs as job_store
from phemius.store.audio import Audio
from phemius.store.documents import NewDocument
from phemius.store.jobs import Job
from tests.models.fakes import FakeScriptModel, RecordingScriptModel, UseScriptModel

HEADINGS = ["Setup", "Usage", "Upgrades"]
SUMMARY = "Explains how deploys roll out."
# With the smallest token budget a section holds 2,000 characters, so each of
# these 1,500-character headings becomes a section of its own.
LONG_TEXT = "\n\n".join(
    f"## {heading}\n\n" + " ".join(["Deploys roll out in waves."] * 55)
    for heading in HEADINGS
)


class SectionScriptModel(RecordingScriptModel):
    """Writes a script naming its section; fails the call numbered `failing_call`."""

    def __init__(self, failing_call: int | None = None) -> None:
        super().__init__()
        self.failing_call = failing_call

    def write_script(
        self,
        title: str,
        text: str,
        tone: str,
        section: SectionContext | None = None,
    ) -> Script:
        super().write_script(title, text, tone, section)
        if len(self.sections) == self.failing_call:
            raise ModelError("Model output hit the 1-token limit.", hint="Raise it.")
        name = section.title if section else title
        return Script(f"Script for {name}.", TokenUsage(1000, 200))


class CancellingScriptModel(SectionScriptModel):
    def __init__(self, job_id: int) -> None:
        super().__init__()
        self.job_id = job_id

    def write_script(
        self,
        title: str,
        text: str,
        tone: str,
        section: SectionContext | None = None,
    ) -> Script:
        queue.cancel_job(self.job_id)
        return super().write_script(title, text, tone, section)


@pytest.fixture(autouse=True)
def library(isolated_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_MAX_TOKENS", "1")
    database.init_database(isolated_env / "library.db")


def _queue_audio(text: str = LONG_TEXT) -> int:
    stored = document_store.add_document(
        NewDocument(
            title="Guide",
            source="guide.md",
            text=text,
            category="how-to",
            summary=SUMMARY,
            suggested_tone="teacher",
            tone_rationale="Teacher suits a guide.",
            audio_suitability="recommended",
            suitability_reason="Mostly prose.",
            suitability_source="model",
        )
    )
    return pipeline.build_audio(stored.document_id).job_id


def _job(job_id: int) -> Job:
    job = job_store.get_job(job_id)
    assert job is not None
    return job


def _audio(job_id: int) -> Audio:
    audio_id = _job(job_id)["audio_id"]
    assert audio_id is not None
    audio = audio_store.get_audio(audio_id)
    assert audio is not None
    return audio


def test_a_long_document_is_written_section_by_section_in_order(
    use_script_model: UseScriptModel,
) -> None:
    model = SectionScriptModel()
    use_script_model(model)
    job_id = _queue_audio()

    assert runner.run_next("writing_script")

    sections = [section for section in model.sections if section is not None]
    assert [(section.title, section.number) for section in sections] == [
        ("Setup", 1),
        ("Usage", 2),
        ("Upgrades", 3),
    ]
    assert {section.count for section in sections} == {3}
    assert sections[0].continuity == ""
    assert SUMMARY in sections[2].continuity
    assert "Setup; Usage" in sections[2].continuity
    assert "Script for Usage." in sections[2].continuity
    audio = _audio(job_id)
    assert audio["section_titles"] == HEADINGS
    assert audio["script"] == "\n\n".join(f"Script for {name}." for name in HEADINGS)


def test_a_short_document_is_one_request_without_a_section_brief(
    use_script_model: UseScriptModel,
) -> None:
    model = SectionScriptModel()
    use_script_model(model)
    job_id = _queue_audio("Install it with uv.")

    assert runner.run_next("writing_script")

    assert model.sections == [None]
    assert _audio(job_id)["section_titles"] == ["Guide"]


def test_usage_is_summed_over_sections(
    use_script_model: UseScriptModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_INPUT_PRICE", "3")
    monkeypatch.setenv("PHEMIUS_SCRIPT_OUTPUT_PRICE", "15")
    use_script_model(SectionScriptModel())
    job_id = _queue_audio()

    assert runner.run_next("writing_script")

    job = _job(job_id)
    assert (job["input_tokens"], job["output_tokens"]) == (3000, 600)
    assert job["cost_usd"] == pytest.approx(0.018)


def test_one_unreported_section_leaves_the_total_unknown(
    use_script_model: UseScriptModel,
) -> None:
    use_script_model(FakeScriptModel(usage=TokenUsage(None, 200)))
    job_id = _queue_audio()

    assert runner.run_next("writing_script")

    job = _job(job_id)
    assert (job["input_tokens"], job["output_tokens"]) == (None, 600)


def test_a_truncated_section_fails_the_job_without_a_partial_script(
    use_script_model: UseScriptModel,
) -> None:
    use_script_model(SectionScriptModel(failing_call=2))
    job_id = _queue_audio()

    assert runner.run_next("writing_script")

    job = _job(job_id)
    audio = _audio(job_id)
    assert (job["state"], job["hint"]) == ("failed", "Raise it.")
    assert (audio["script"], audio["section_titles"]) == (None, [])
    assert job["input_tokens"] is None


def test_a_retry_after_a_failed_section_leaves_one_set_of_sections(
    use_script_model: UseScriptModel,
) -> None:
    use_script_model(SectionScriptModel(failing_call=3))
    job_id = _queue_audio()
    assert runner.run_next("writing_script")

    use_script_model(SectionScriptModel())
    queue.retry_job(job_id)
    assert runner.run_next("writing_script")

    assert _job(job_id)["stage"] == "narrating"
    assert _audio(job_id)["section_titles"] == HEADINGS


def test_cancelling_between_sections_writes_no_more_and_records_nothing(
    use_script_model: UseScriptModel,
) -> None:
    job_id = _queue_audio()
    model = CancellingScriptModel(job_id)
    use_script_model(model)

    assert runner.run_next("writing_script")

    audio = _audio(job_id)
    assert len(model.sections) == 1
    assert _job(job_id)["state"] == "cancelled"
    assert (audio["script"], audio["section_titles"]) == (None, [])


def test_a_stopping_runner_writes_no_more_sections(
    use_script_model: UseScriptModel,
) -> None:
    model = SectionScriptModel()
    use_script_model(model)
    job_id = _queue_audio()
    claimed = job_store.claim_next("writing_script")
    assert claimed is not None

    is_current = pipeline.write_script(claimed, lambda: len(model.sections) >= 1)

    assert is_current is False
    assert len(model.sections) == 1
    # Left running, so the next start fails it as interrupted.
    assert _job(job_id)["state"] == "running"
    assert _audio(job_id)["script"] is None
