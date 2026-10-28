"""Background workers that run queued jobs, one stage at a time.

`script_workers` threads write scripts in parallel; a single thread narrates,
because local voice models are heavy. Each worker claims the oldest job waiting
for its stage, so a job moves from one pool to the other between stages.
"""

import threading
from collections.abc import Callable

import structlog

from phemius.config import load_config
from phemius.errors import PhemiusError
from phemius.services import pipeline, queue
from phemius.store import jobs as job_store
from phemius.store.jobs import ClaimedJob, JobStage

log = structlog.get_logger(__name__)

# Workers also wake on `queue.notify_workers()`; polling is the fallback.
POLL_SECONDS = 1.0
STOP_TIMEOUT_SECONDS = 5.0

type StageHandler = Callable[[ClaimedJob], bool]

STAGE_HANDLERS: dict[JobStage, StageHandler] = {
    "writing_script": pipeline.write_script,
    "narrating": pipeline.narrate,
}


class JobRunner:
    def __init__(self, script_workers: int) -> None:
        self._is_stopping = threading.Event()
        script_stages: list[JobStage] = ["writing_script"] * script_workers
        stages = [*script_stages, "narrating"]
        self._threads = [
            threading.Thread(
                target=self._work, args=(stage,), name=f"job-{stage}", daemon=True
            )
            for stage in stages
        ]

    def start(self) -> None:
        for thread in self._threads:
            thread.start()

    def stop(self) -> None:
        """Stop picking up jobs. A step still running is failed on next start."""
        self._is_stopping.set()
        queue.notify_workers()
        for thread in self._threads:
            thread.join(STOP_TIMEOUT_SECONDS)

    def _work(self, stage: JobStage) -> None:
        while not self._is_stopping.is_set():
            seen_count = queue.work_signal.count
            try:
                has_run = run_next(stage)
            except Exception as error:  # a busy or broken library must not kill it
                log.error(
                    "job_runner_error", stage=stage, error_type=type(error).__name__
                )
                has_run = False
            if not has_run:
                queue.work_signal.wait(seen_count, POLL_SECONDS)


def start_runner() -> JobRunner:
    """Fail jobs a previous run left running, then start the workers."""
    interrupted = job_store.fail_interrupted_jobs()
    if interrupted:
        log.warning("jobs_interrupted", count=interrupted)
    script_workers = load_config().script_workers
    runner = JobRunner(script_workers)
    runner.start()
    log.info("job_runner_started", script_workers=script_workers)
    return runner


def run_next(stage: JobStage) -> bool:
    """Run the oldest job waiting for `stage`. False when there was none."""
    job = job_store.claim_next(stage)
    if job is None:
        return False
    run_stage(job)
    return True


def run_stage(job: ClaimedJob) -> None:
    log.info("job_started", job_id=job.id, stage=job.stage, attempt=job.attempt)
    try:
        is_current = STAGE_HANDLERS[job.stage](job)
    except Exception as error:  # stored on the job and shown in the queue
        message, hint = _error_parts(error)
        job_store.fail_job(job, message, hint)
        log.warning(
            "job_failed",
            job_id=job.id,
            stage=job.stage,
            error_type=type(error).__name__,
        )
        return
    log.info(
        "job_stage_finished", job_id=job.id, stage=job.stage, is_current=is_current
    )
    queue.notify_workers()


def _error_parts(error: Exception) -> tuple[str, str | None]:
    if isinstance(error, PhemiusError):
        return error.message, error.hint
    return str(error) or type(error).__name__, None
