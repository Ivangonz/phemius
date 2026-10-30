"""Generated audio for a document: one row per tone and voice combination.

An audio's status, stage and error come from its job (see `store/jobs.py`).
"""

import sqlite3
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypedDict, cast

from phemius.store.database import transaction
from phemius.store.jobs import AudioFormat, JobStage, JobState

# Selected with `audio a JOIN jobs j ON j.audio_id = a.id`; every audio has a job.
AUDIO_JOB_COLUMNS = (
    "j.id AS job_id, j.state AS status, j.stage, j.error_message AS error,"
    " j.error_hint AS hint"
)


class AudioSummary(TypedDict):
    id: int
    version: int | None
    tone: str
    voice: str | None
    job_id: int
    status: JobState
    stage: JobStage
    error: str | None
    hint: str | None
    # In script order; empty before the script is written.
    section_titles: list[str]


class Chapter(TypedDict):
    title: str
    # Where the section starts in the audio; None until it is narrated.
    start_seconds: float | None


class Audio(TypedDict):
    id: int
    doc_id: int
    version_id: int | None
    tone: str
    voice: str | None
    script: str | None
    path: str | None
    format: AudioFormat | None
    size_bytes: int | None
    duration_seconds: float | None
    conversion_note: str | None
    created: float
    job_id: int
    status: JobState
    stage: JobStage
    error: str | None
    hint: str | None
    section_titles: list[str]
    # One per script section, in order; empty before the script is written.
    chapters: list[Chapter]


@dataclass(frozen=True)
class ScriptInput:
    title: str
    text: str
    tone: str
    summary: str


def get_audio(audio_id: int) -> Audio | None:
    with transaction() as connection:
        row = connection.execute(
            f"SELECT a.*, {AUDIO_JOB_COLUMNS}"
            " FROM audio a JOIN jobs j ON j.audio_id = a.id WHERE a.id = ?",
            (audio_id,),
        ).fetchone()
        chapters = _chapters(connection, audio_id)
    if row is None:
        return None
    titles = [chapter["title"] for chapter in chapters]
    return cast(Audio, {**dict(row), "section_titles": titles, "chapters": chapters})


def _chapters(connection: sqlite3.Connection, audio_id: int) -> list[Chapter]:
    rows = connection.execute(
        "SELECT title, start_seconds FROM audio_sections WHERE audio_id = ?"
        " ORDER BY position",
        (audio_id,),
    )
    return [
        Chapter(title=row["title"], start_seconds=row["start_seconds"]) for row in rows
    ]


def section_scripts(audio_id: int) -> list[str]:
    """The audio's section scripts in order; empty for audio written before #31."""
    with transaction() as connection:
        rows = connection.execute(
            "SELECT script FROM audio_sections WHERE audio_id = ? ORDER BY position",
            (audio_id,),
        ).fetchall()
    return [row["script"] for row in rows]


def existing_audio_ids(audio_ids: Sequence[int]) -> set[int]:
    """Those of `audio_ids` still in the library."""
    marks = ", ".join("?" * len(audio_ids))
    with transaction() as connection:
        rows = connection.execute(
            f"SELECT id FROM audio WHERE id IN ({marks})", list(audio_ids)
        ).fetchall()
    return {row["id"] for row in rows}


def section_titles(
    connection: sqlite3.Connection, audio_ids: Sequence[int]
) -> defaultdict[int, list[str]]:
    """Each audio's section titles in order, in one query for all of them."""
    marks = ", ".join("?" * len(audio_ids))
    rows = connection.execute(
        f"SELECT audio_id, title FROM audio_sections WHERE audio_id IN ({marks})"
        " ORDER BY audio_id, position",
        list(audio_ids),
    )
    titles: defaultdict[int, list[str]] = defaultdict(list)
    for row in rows:
        titles[row["audio_id"]].append(row["title"])
    return titles


def get_script_input(audio_id: int) -> ScriptInput | None:
    """The text of the version this audio narrates, or None if it is missing."""
    with transaction() as connection:
        row = connection.execute(
            "SELECT v.title, v.text, a.tone, COALESCE(v.summary, '') AS summary"
            " FROM audio a JOIN doc_versions v ON v.id = a.version_id"
            " WHERE a.id = ?",
            (audio_id,),
        ).fetchone()
    return ScriptInput(**dict(row)) if row else None
