"""The job queue as users see it: list, cancel, retry, pause and resume."""

import threading
from typing import NoReturn

import structlog

from phemius.errors import JobStateError, NotFoundError
from phemius.store import jobs as job_store
from phemius.store.jobs import Job, JobPage, JobState

log = structlog.get_logger(__name__)


class WorkSignal:
    """Wakes idle workers. Counting signals means one sent while a worker was
    busy claiming is not lost: the worker sees the count changed and skips the
    wait."""

    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._count = 0

    @property
    def count(self) -> int:
        with self._condition:
            return self._count

    def notify(self) -> None:
        with self._condition:
            self._count += 1
            self._condition.notify_all()

    def wait(self, seen_count: int, timeout_seconds: float) -> None:
        with self._condition:
            self._condition.wait_for(lambda: self._count != seen_count, timeout_seconds)


work_signal = WorkSignal()


def notify_workers() -> None:
    """Wake idle workers so new or retried work starts without waiting a poll."""
    work_signal.notify()


def list_jobs(states: list[JobState], limit: int, offset: int) -> JobPage:
    return job_store.list_jobs(states, limit, offset)


def cancel_job(job_id: int) -> Job:
    """Cancel a waiting job, or a running one at the end of its current step."""
    if not job_store.cancel_job(job_id):
        _raise_for_state(job_id, "Only queued or running jobs can be cancelled.")
    log.info("job_cancelled", job_id=job_id)
    return _get_job(job_id)


def retry_job(job_id: int) -> Job:
    if not job_store.retry_job(job_id):
        _raise_for_state(job_id, "Only failed or cancelled jobs can be retried.")
    log.info("job_retried", job_id=job_id)
    notify_workers()
    return _get_job(job_id)


def pause_queue() -> None:
    """Stop workers from picking up jobs; running steps finish first."""
    job_store.set_queue_paused(True)
    log.info("queue_paused")


def resume_queue() -> None:
    job_store.set_queue_paused(False)
    log.info("queue_resumed")
    notify_workers()


def is_queue_paused() -> bool:
    return job_store.is_queue_paused()


def _get_job(job_id: int) -> Job:
    job = job_store.get_job(job_id)
    if job is None:
        raise NotFoundError(f"Job {job_id} not found")
    return job


def _raise_for_state(job_id: int, hint: str) -> NoReturn:
    job = _get_job(job_id)
    raise JobStateError(f"Job {job_id} is {job['state']}", hint=hint)
