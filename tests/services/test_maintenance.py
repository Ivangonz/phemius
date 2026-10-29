import threading
from pathlib import Path

import pytest

from phemius.errors import LibraryBusyError
from phemius.services import maintenance, runner
from phemius.store import database
from tests.services.test_runner import _job, _queue_audio


@pytest.fixture(autouse=True)
def library(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")


def test_workers_claim_nothing_while_the_gate_is_closed() -> None:
    job_id = _queue_audio()

    with maintenance.gate.exclusive():
        has_run = runner.run_next("writing_script")
        state_during = _job(job_id)["state"]

    assert (has_run, state_during) == (False, "queued")
    assert runner.run_next("writing_script") is True


def test_a_second_library_operation_is_refused() -> None:
    with maintenance.gate.exclusive():
        with pytest.raises(LibraryBusyError, match="Another library operation"):
            with maintenance.gate.exclusive():
                pass


def test_a_worker_still_in_its_turn_makes_the_gate_refuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(maintenance, "DRAIN_SECONDS", 0.05)
    has_entered = threading.Event()
    release = threading.Event()

    def hold_a_turn() -> None:
        with maintenance.gate.worker_turn():
            has_entered.set()
            release.wait(timeout=5)

    worker = threading.Thread(target=hold_a_turn)
    worker.start()
    has_entered.wait(timeout=5)
    try:
        with pytest.raises(LibraryBusyError, match="A job is running"):
            with maintenance.gate.exclusive():
                pass
    finally:
        release.set()
        worker.join()

    with maintenance.gate.exclusive():
        pass
