"""Persisted background jobs and the queue's paused flag.

The job vocabulary below is the one every screen and endpoint reuses:

- `state`: `queued` (waiting for a worker), `running`, `done`, `failed` or
  `cancelled`.
- `stage`: the step a job is waiting for or running, `writing_script` then
  `narrating`.

Workers fence their writes with `attempts`: a retry bumps it, so a worker that
was cancelled mid-call and finishes late cannot overwrite the new attempt.
"""

import sqlite3
import time
from dataclasses import dataclass
from typing import Literal, TypedDict, cast

from phemius.store.database import transaction

type JobType = Literal["audio"]
type JobState = Literal["queued", "running", "done", "failed", "cancelled"]
type JobStage = Literal["writing_script", "narrating"]

INTERRUPTED_MESSAGE = "Interrupted by a restart"
INTERRUPTED_HINT = "Retry the job to run it again."


class Job(TypedDict):
    id: int
    type: JobType
    state: JobState
    stage: JobStage
    # Fraction of the current stage, 0 to 1.
    progress: float
    error: str | None
    hint: str | None
    attempts: int
    audio_id: int | None
    document_id: int | None
    version: int | None
    title: str | None
    tone: str | None
    voice: str | None
    created: float
    started: float | None
    updated: float
    finished: float | None


@dataclass(frozen=True)
class JobPage:
    items: list[Job]
    total: int


@dataclass(frozen=True)
class QueuedAudio:
    audio_id: int
    job_id: int


@dataclass(frozen=True)
class ClaimedJob:
    id: int
    audio_id: int
    stage: JobStage
    attempt: int


_JOB_COLUMNS = (
    "j.id, j.type, j.state, j.stage, j.progress, j.error_message AS error,"
    " j.error_hint AS hint, j.attempts, j.audio_id, a.doc_id AS document_id,"
    " v.number AS version, v.title, a.tone, a.voice, j.created, j.started,"
    " j.updated, j.finished"
    " FROM jobs j LEFT JOIN audio a ON a.id = j.audio_id"
    " LEFT JOIN doc_versions v ON v.id = j.version_id"
)


def enqueue_audio(
    document_id: int, version_id: int, tone: str, voice: str
) -> QueuedAudio:
    """Create an audio record and its queued job together."""
    now = time.time()
    with transaction() as connection:
        audio_id = connection.execute(
            "INSERT INTO audio (doc_id, version_id, tone, voice, created)"
            " VALUES (?, ?, ?, ?, ?)",
            (document_id, version_id, tone, voice, now),
        ).lastrowid
        job_id = connection.execute(
            "INSERT INTO jobs (type, audio_id, version_id, state, stage, created,"
            " updated) VALUES ('audio', ?, ?, 'queued', 'writing_script', ?, ?)",
            (audio_id, version_id, now, now),
        ).lastrowid
    return QueuedAudio(audio_id=cast(int, audio_id), job_id=cast(int, job_id))


def get_job(job_id: int) -> Job | None:
    with transaction() as connection:
        row = connection.execute(
            f"SELECT {_JOB_COLUMNS} WHERE j.id = ?", (job_id,)
        ).fetchone()
    return cast(Job, dict(row)) if row else None


def list_jobs(states: list[JobState], limit: int, offset: int) -> JobPage:
    """One page of jobs in `states` (all when empty), newest first."""
    where = f"WHERE j.state IN ({', '.join('?' * len(states))})" if states else ""
    with transaction() as connection:
        total: int = connection.execute(
            f"SELECT COUNT(*) FROM jobs j {where}", states
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT {_JOB_COLUMNS} {where}"
            " ORDER BY j.created DESC, j.id DESC LIMIT ? OFFSET ?",
            [*states, limit, offset],
        ).fetchall()
    return JobPage(items=[cast(Job, dict(row)) for row in rows], total=total)


def claim_next(stage: JobStage) -> ClaimedJob | None:
    """Mark the oldest job waiting for `stage` as running, unless paused."""
    with transaction(is_immediate=True) as connection:
        if _is_paused(connection):
            return None
        row = connection.execute(
            "SELECT id, audio_id, stage, attempts FROM jobs"
            " WHERE state = 'queued' AND stage = ? ORDER BY created, id LIMIT 1",
            (stage,),
        ).fetchone()
        if row is None:
            return None
        now = time.time()
        connection.execute(
            "UPDATE jobs SET state = 'running', progress = 0,"
            " started = COALESCE(started, ?), updated = ? WHERE id = ?",
            (now, now, row["id"]),
        )
    return ClaimedJob(row["id"], row["audio_id"], row["stage"], row["attempts"])


def finish_script(job: ClaimedJob, script: str) -> bool:
    """Save the script and queue the job for narration. False if superseded."""
    with transaction() as connection:
        if not _advance(
            connection,
            job,
            "state = 'queued', stage = 'narrating', progress = 0",
        ):
            return False
        connection.execute(
            "UPDATE audio SET script = ? WHERE id = ?", (script, job.audio_id)
        )
    return True


def finish_audio(job: ClaimedJob, path: str) -> bool:
    """Save the audio file path and mark the job done. False if superseded."""
    with transaction() as connection:
        if not _advance(
            connection, job, "state = 'done', progress = 1, finished = :now"
        ):
            return False
        connection.execute(
            "UPDATE audio SET path = ? WHERE id = ?", (path, job.audio_id)
        )
    return True


def fail_job(job: ClaimedJob, message: str, hint: str | None) -> bool:
    with transaction() as connection:
        return _advance(
            connection,
            job,
            "state = 'failed', error_message = :message, error_hint = :hint,"
            " finished = :now",
            message=message,
            hint=hint,
        )


def _advance(
    connection: sqlite3.Connection,
    job: ClaimedJob,
    assignments: str,
    **parameters: object,
) -> bool:
    cursor = connection.execute(
        f"UPDATE jobs SET {assignments}, updated = :now"
        " WHERE id = :id AND state = 'running' AND attempts = :attempt",
        {**parameters, "now": time.time(), "id": job.id, "attempt": job.attempt},
    )
    return cursor.rowcount == 1


def cancel_job(job_id: int) -> bool:
    """Cancel a queued or running job. False if it is in another state."""
    now = time.time()
    with transaction() as connection:
        cursor = connection.execute(
            "UPDATE jobs SET state = 'cancelled', updated = ?, finished = ?"
            " WHERE id = ? AND state IN ('queued', 'running')",
            (now, now, job_id),
        )
    return cursor.rowcount == 1


def retry_job(job_id: int) -> bool:
    """Queue a failed or cancelled job again. False if it is in another state.

    A job whose script was already written resumes at narration, so a voice
    failure does not spend model credits on a second script.
    """
    with transaction() as connection:
        cursor = connection.execute(
            "UPDATE jobs SET state = 'queued', progress = 0,"
            " stage = CASE WHEN (SELECT script FROM audio WHERE id = jobs.audio_id)"
            " IS NULL THEN 'writing_script' ELSE 'narrating' END,"
            " error_message = NULL, error_hint = NULL, attempts = attempts + 1,"
            " started = NULL, finished = NULL, updated = ?"
            " WHERE id = ? AND state IN ('failed', 'cancelled')",
            (time.time(), job_id),
        )
    return cursor.rowcount == 1


def fail_interrupted_jobs() -> int:
    """Fail every running job; none survives a restart. Returns how many."""
    now = time.time()
    with transaction() as connection:
        cursor = connection.execute(
            "UPDATE jobs SET state = 'failed', error_message = ?, error_hint = ?,"
            " updated = ?, finished = ? WHERE state = 'running'",
            (INTERRUPTED_MESSAGE, INTERRUPTED_HINT, now, now),
        )
    return cursor.rowcount


def is_queue_paused() -> bool:
    with transaction() as connection:
        return _is_paused(connection)


def set_queue_paused(is_paused: bool) -> None:
    with transaction() as connection:
        connection.execute("UPDATE queue SET is_paused = ?", (is_paused,))


def _is_paused(connection: sqlite3.Connection) -> bool:
    row = connection.execute("SELECT is_paused FROM queue").fetchone()
    return bool(row["is_paused"])
