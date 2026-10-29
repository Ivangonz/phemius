from pathlib import Path

import pytest

from phemius.store import audio as audio_store
from phemius.store import database
from phemius.store import documents as document_store
from phemius.store import jobs as job_store
from phemius.store.documents import NewDocument
from phemius.store.jobs import ClaimedJob, JobUsage, ScriptSection

NO_USAGE = JobUsage(None, None, None)


@pytest.fixture(autouse=True)
def library(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")


def _claimed_job() -> ClaimedJob:
    stored = document_store.add_document(
        NewDocument(
            title="Guide",
            source="guide.md",
            text="Install it.",
            category="how-to",
            summary="A guide.",
            suggested_tone="teacher",
            tone_rationale="Teacher suits a guide.",
            audio_suitability="recommended",
            suitability_reason="Mostly prose.",
            suitability_source="model",
        )
    )
    document = document_store.get_document(stored.document_id)
    assert document is not None
    job_store.enqueue_audio(stored.document_id, document["version_id"], "teacher", "a")
    job = job_store.claim_next("writing_script")
    assert job is not None
    return job


def test_rewriting_a_script_replaces_its_sections() -> None:
    job = _claimed_job()
    job_store.finish_script(job, "Old.", [ScriptSection("Old", "Old.")], NO_USAGE)
    with database.transaction() as connection:
        connection.execute("UPDATE jobs SET state = 'running' WHERE id = ?", (job.id,))
    sections = [ScriptSection("One", "First."), ScriptSection("Two", "Second.")]

    assert job_store.finish_script(job, "First.\n\nSecond.", sections, NO_USAGE)

    audio = audio_store.get_audio(job.audio_id)
    assert audio is not None
    assert audio["section_titles"] == ["One", "Two"]


def test_a_superseded_job_saves_no_sections() -> None:
    job = _claimed_job()
    job_store.cancel_job(job.id)

    saved = job_store.finish_script(
        job, "Late.", [ScriptSection("A", "Late.")], NO_USAGE
    )

    audio = audio_store.get_audio(job.audio_id)
    assert audio is not None
    assert saved is False
    assert (audio["script"], audio["section_titles"]) == (None, [])
    assert job_store.is_current(job) is False
