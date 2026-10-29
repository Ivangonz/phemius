import sqlite3
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from phemius.errors import LibraryBusyError
from phemius.services import documents, maintenance
from phemius.store import audio as audio_store
from phemius.store import database
from phemius.store import documents as document_store
from phemius.store import jobs as job_store
from phemius.store.documents import NewDocument
from phemius.store.jobs import AudioFile


@pytest.fixture
def narrated(isolated_env: Path) -> tuple[int, Path]:
    """A document with one finished audio file; no runner, so nothing races."""
    database.init_database(isolated_env / "library.db")
    stored = document_store.add_document(
        NewDocument(
            title="Secret plans",
            source="/docs/plans.md",
            text="# Secret plans",
            category="reference",
            summary="Plans.",
            suggested_tone="teacher",
            tone_rationale="Clear.",
            audio_suitability="recommended",
            suitability_reason="Prose.",
            suitability_source="model",
        )
    )
    document = document_store.get_document(stored.document_id)
    assert document is not None
    queued = job_store.enqueue_audio(
        document["id"], document["version_id"], "teacher", "stub:silent"
    )
    job = job_store.claim_next("writing_script")
    assert job is not None
    path = isolated_env / "audio" / f"{queued.audio_id}.wav"
    path.parent.mkdir()
    path.write_bytes(b"RIFF")
    assert job_store.finish_audio(job, AudioFile(str(path), "wav", 4))
    return document["id"], path


def test_a_failure_mid_delete_leaves_everything_in_place(
    narrated: tuple[int, Path],
) -> None:
    document_id, path = narrated
    with database.transaction() as connection:
        connection.execute(
            "CREATE TRIGGER fail_delete BEFORE DELETE ON docs"
            " BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )

    with pytest.raises(sqlite3.IntegrityError):
        documents.delete_document(document_id)

    page = document_store.list_versions(document_id, limit=25, offset=0)
    assert page is not None
    [version] = page.items
    assert [audio["status"] for audio in version["audio"]] == ["done"]
    assert path.exists()


def test_delete_is_refused_while_a_backup_holds_the_library(
    narrated: tuple[int, Path],
) -> None:
    document_id, path = narrated

    with maintenance.gate.exclusive(), pytest.raises(LibraryBusyError) as error:
        documents.delete_document(document_id)

    assert error.value.hint
    assert document_store.get_document(document_id) is not None
    assert path.exists()


def test_delete_logs_the_document_id_only(narrated: tuple[int, Path]) -> None:
    document_id, _path = narrated

    with capture_logs() as logs:
        documents.delete_document(document_id)

    [entry] = [log for log in logs if log["event"] == "document_deleted"]
    assert entry["document_id"] == document_id
    assert "Secret plans" not in repr(logs)
    assert "plans.md" not in repr(logs)


def test_a_cancelled_job_finishing_late_does_not_bring_audio_back(
    narrated: tuple[int, Path],
) -> None:
    document_id, _path = narrated
    document = document_store.get_document(document_id)
    assert document is not None
    queued = job_store.enqueue_audio(
        document_id, document["version_id"], "teacher", "stub:silent"
    )
    job = job_store.claim_next("writing_script")
    assert job is not None
    job_store.cancel_job(queued.job_id)

    documents.delete_document(document_id)

    usage = job_store.JobUsage(None, None, None)
    assert job_store.finish_script(job, "A script.", [], usage) is False
    assert job_store.finish_audio(job, AudioFile("/x.wav", "wav", 1)) is False
    assert job_store.fail_job(job, "Late.", None) is False
    assert audio_store.get_audio(queued.audio_id) is None
