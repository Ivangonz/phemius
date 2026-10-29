"""Keeps job workers and whole-library operations (backup, restore, delete all
audio) apart.

Workers take a turn for each claim-and-run step. A library operation closes
the gate to new turns, refuses to start while a job is running, and otherwise
waits briefly for workers that are only looking for work. While it holds the
gate no worker claims a job, so the library's files and rows stay still.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from phemius.errors import LibraryBusyError
from phemius.services import queue
from phemius.store import jobs as job_store

# A worker between turns finishes its claim in milliseconds; one that has not
# left by then is running a job.
DRAIN_SECONDS = 2.0

JOB_RUNNING_HINT = (
    "Wait for the running job to finish, or cancel it in the queue, then try again."
)


class MaintenanceGate:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._active_turns = 0
        self._is_closed = False

    @contextmanager
    def worker_turn(self) -> Iterator[bool]:
        """Yields False, so the worker skips this round, while the gate is closed."""
        with self._condition:
            if self._is_closed:
                is_allowed = False
            else:
                is_allowed = True
                self._active_turns += 1
        try:
            yield is_allowed
        finally:
            if is_allowed:
                with self._condition:
                    self._active_turns -= 1
                    self._condition.notify_all()

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        self._close()
        try:
            self._refuse_if_job_running()
            yield
        finally:
            with self._condition:
                self._is_closed = False
            queue.notify_workers()

    def _close(self) -> None:
        with self._condition:
            if self._is_closed:
                raise LibraryBusyError(
                    "Another library operation is in progress.",
                    hint="Wait for it to finish, then try again.",
                )
            self._is_closed = True

    def _refuse_if_job_running(self) -> None:
        if job_store.has_running_jobs() or not self._wait_for_workers():
            raise LibraryBusyError("A job is running.", hint=JOB_RUNNING_HINT)

    def _wait_for_workers(self) -> bool:
        with self._condition:
            return self._condition.wait_for(
                lambda: self._active_turns == 0, DRAIN_SECONDS
            )


gate = MaintenanceGate()
