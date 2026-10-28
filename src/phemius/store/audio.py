"""Generated audio for a document: one row per tone and voice combination.

An audio's status, stage and error come from its job (see `store/jobs.py`).
"""

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
    conversion_note: str | None
    created: float
    job_id: int
    status: JobState
    stage: JobStage
    error: str | None
    hint: str | None


@dataclass(frozen=True)
class ScriptInput:
    title: str
    text: str
    tone: str


def get_audio(audio_id: int) -> Audio | None:
    with transaction() as connection:
        row = connection.execute(
            f"SELECT a.*, {AUDIO_JOB_COLUMNS}"
            " FROM audio a JOIN jobs j ON j.audio_id = a.id WHERE a.id = ?",
            (audio_id,),
        ).fetchone()
    return cast(Audio, dict(row)) if row else None


def get_script_input(audio_id: int) -> ScriptInput | None:
    """The text of the version this audio narrates, or None if it is missing."""
    with transaction() as connection:
        row = connection.execute(
            "SELECT v.title, v.text, a.tone FROM audio a"
            " JOIN doc_versions v ON v.id = a.version_id WHERE a.id = ?",
            (audio_id,),
        ).fetchone()
    return ScriptInput(row["title"], row["text"], row["tone"]) if row else None
