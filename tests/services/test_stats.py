from datetime import date
from pathlib import Path

import pytest
from freezegun import freeze_time

from phemius.services.stats import today_stats
from phemius.store import database
from phemius.store import documents as document_store
from phemius.store import jobs as job_store
from phemius.store.documents import NewDocument
from phemius.store.jobs import AudioFile, JobUsage

UTC_PLUS_ONE = 60


@pytest.fixture(autouse=True)
def library(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")
    document_store.add_document(
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


def _write_script(cost_usd: float | None) -> None:
    document = document_store.get_document(1)
    assert document is not None
    job_store.enqueue_audio(1, document["version_id"], "teacher", "stub:silent")
    job = job_store.claim_next("writing_script")
    assert job is not None
    job_store.finish_script(job, "Script.", JobUsage(100, 50, cost_usd))


def _narrate(duration_seconds: float) -> None:
    job = job_store.claim_next("narrating")
    assert job is not None
    job_store.finish_audio(job, AudioFile("1.wav", "wav", 44, duration_seconds))


def _seed_two_days() -> None:
    with freeze_time("2026-10-27 23:30:00"):
        _write_script(cost_usd=0.01)
        _narrate(duration_seconds=60)
    with freeze_time("2026-10-28 09:00:00"):
        _write_script(cost_usd=0.02)
        _narrate(duration_seconds=90)
        _write_script(cost_usd=None)


@freeze_time("2026-10-28 18:00:00")
def test_today_counts_only_work_done_since_midnight_utc() -> None:
    _seed_two_days()

    stats = today_stats()

    assert stats.date == date(2026, 10, 28)
    assert (stats.scripts_written, stats.audio_files) == (2, 1)
    assert stats.narration_minutes == 1.5
    assert stats.estimated_cost_usd == pytest.approx(0.02)
    assert stats.unpriced_scripts == 1


@freeze_time("2026-10-28 18:00:00")
def test_today_follows_the_callers_utc_offset() -> None:
    _seed_two_days()

    stats = today_stats(utc_offset_minutes=UTC_PLUS_ONE)

    assert (stats.scripts_written, stats.audio_files) == (3, 2)
    assert stats.narration_minutes == 2.5
    assert stats.estimated_cost_usd == pytest.approx(0.03)


@freeze_time("2026-10-28 23:30:00")
def test_a_positive_offset_can_already_be_tomorrow() -> None:
    _seed_two_days()

    stats = today_stats(utc_offset_minutes=UTC_PLUS_ONE)

    assert stats.date == date(2026, 10, 29)
    assert stats.scripts_written == 0


def test_an_empty_day_is_all_zeros_and_costs_nothing() -> None:
    stats = today_stats()

    assert (stats.scripts_written, stats.audio_files, stats.unpriced_scripts) == (
        0,
        0,
        0,
    )
    assert stats.narration_minutes == 0
    assert stats.estimated_cost_usd == 0


def test_cost_is_unknown_when_no_script_today_had_a_price() -> None:
    _write_script(cost_usd=None)

    stats = today_stats()

    assert stats.estimated_cost_usd is None
    assert stats.unpriced_scripts == 1
