import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from phemius.config import Config
from phemius.errors import VoiceError
from phemius.services import pipeline, queue, runner
from phemius.services.runner import JobRunner
from phemius.store import audio as audio_store
from phemius.store import database
from phemius.store import documents as document_store
from phemius.store import jobs as job_store
from phemius.store.audio import Audio
from phemius.store.documents import NewDocument
from phemius.store.jobs import Job, JobState
from phemius.voices import ENGINES, VoiceEngine, stub
from phemius.voices.stub import StubEngine
from tests.models.fakes import FailingScriptModel, FakeScriptModel, UseScriptModel
from tests.services.fakes import FakeFfmpeg, UseFfmpeg

type StartRunner = Callable[[], JobRunner]

FINISHED: set[JobState] = {"done", "failed", "cancelled"}


class CountingScriptModel(FakeScriptModel):
    def __init__(self) -> None:
        super().__init__()
        self.write_calls = 0

    def write_script(self, title: str, text: str, tone: str) -> str:
        self.write_calls += 1
        return self.script


class BlockingScriptModel(FakeScriptModel):
    """Holds a script call open until the test releases it."""

    def __init__(self) -> None:
        super().__init__()
        self.is_writing = threading.Event()
        self.release = threading.Event()

    def write_script(self, title: str, text: str, tone: str) -> str:
        self.is_writing.set()
        self.release.wait(timeout=5)
        return self.script


class ParallelOnlyScriptModel(FakeScriptModel):
    """Fails unless two scripts are being written at the same time."""

    def __init__(self) -> None:
        super().__init__()
        self.barrier = threading.Barrier(2, timeout=5)

    def write_script(self, title: str, text: str, tone: str) -> str:
        self.barrier.wait()
        return self.script


class FailingVoiceEngine(StubEngine):
    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        raise VoiceError("Voice server returned 500.", hint="Check the server.")


def _failing_voice_engine(config: Config) -> VoiceEngine:
    return FailingVoiceEngine()


@pytest.fixture(autouse=True)
def library(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")


@pytest.fixture
def start_runner() -> Iterator[StartRunner]:
    runners: list[JobRunner] = []

    def start() -> JobRunner:
        runners.append(runner.start_runner())
        return runners[-1]

    yield start
    for started in runners:
        started.stop()


def _queue_audio(text: str = "Install it with uv.") -> int:
    stored = document_store.add_document(
        NewDocument(
            title="Guide",
            source=f"{text}.md",
            text=text,
            category="how-to",
            summary="A guide.",
            suggested_tone="teacher",
            tone_rationale="Teacher suits a guide.",
            audio_suitability="recommended",
            suitability_reason="Mostly prose.",
            suitability_source="model",
        )
    )
    return pipeline.build_audio(stored.document_id).job_id


def _job(job_id: int) -> Job:
    job = job_store.get_job(job_id)
    assert job is not None
    return job


def _audio_of(job: Job) -> Audio:
    assert job["audio_id"] is not None
    audio = audio_store.get_audio(job["audio_id"])
    assert audio is not None
    return audio


def _wait_until_finished(job_id: int) -> Job:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = _job(job_id)
        if job["state"] in FINISHED:
            return job
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish")


def test_queued_audio_is_scripted_and_narrated(start_runner: StartRunner) -> None:
    start_runner()

    job = _wait_until_finished(_queue_audio())

    audio = _audio_of(job)
    assert job["state"] == "done", job["error"]
    assert (job["stage"], job["progress"], job["attempts"]) == ("narrating", 1, 1)
    assert audio["script"] and audio["path"]
    assert Path(audio["path"]).exists()


def test_restart_fails_running_jobs_and_resumes_queued_ones(
    start_runner: StartRunner,
) -> None:
    interrupted_id = _queue_audio("First.")
    waiting_id = _queue_audio("Second.")
    assert job_store.claim_next("writing_script") is not None

    start_runner()

    waiting = _wait_until_finished(waiting_id)
    interrupted = _job(interrupted_id)
    assert waiting["state"] == "done"
    assert interrupted["state"] == "failed"
    assert interrupted["error"] == "Interrupted by a restart"
    assert interrupted["hint"]


def test_cancelled_waiting_job_never_runs(
    start_runner: StartRunner, use_script_model: UseScriptModel
) -> None:
    model = CountingScriptModel()
    use_script_model(model)
    cancelled_id = _queue_audio("First.")
    later_id = _queue_audio("Second.")

    queue.cancel_job(cancelled_id)
    start_runner()

    assert _wait_until_finished(later_id)["state"] == "done"
    assert _job(cancelled_id)["state"] == "cancelled"
    assert model.write_calls == 1


def test_cancelling_a_running_job_discards_its_late_result(
    start_runner: StartRunner,
    use_script_model: UseScriptModel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_WORKERS", "1")
    model = BlockingScriptModel()
    use_script_model(model)
    start_runner()
    running_id = _queue_audio("First.")
    assert model.is_writing.wait(timeout=5)

    queue.cancel_job(running_id)
    later_id = _queue_audio("Second.")
    model.release.set()

    assert _wait_until_finished(later_id)["state"] == "done"
    cancelled = _job(running_id)
    assert cancelled["state"] == "cancelled"
    assert _audio_of(cancelled)["script"] is None


def test_model_error_message_and_hint_are_stored(
    start_runner: StartRunner, use_script_model: UseScriptModel
) -> None:
    use_script_model(FailingScriptModel())
    start_runner()

    job = _wait_until_finished(_queue_audio())

    assert job["state"] == "failed"
    assert (job["error"], job["hint"]) == (
        "Provider returned 402.",
        "Add provider credits.",
    )


def test_retry_requeues_a_failed_job(
    start_runner: StartRunner, use_script_model: UseScriptModel
) -> None:
    use_script_model(FailingScriptModel())
    start_runner()
    job_id = _queue_audio()
    _wait_until_finished(job_id)

    use_script_model(FakeScriptModel())
    queue.retry_job(job_id)

    job = _wait_until_finished(job_id)
    assert job["state"] == "done", job["error"]
    assert (job["attempts"], job["error"], job["hint"]) == (2, None, None)


def test_retry_after_a_voice_failure_reuses_the_written_script(
    start_runner: StartRunner,
    use_script_model: UseScriptModel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = CountingScriptModel()
    use_script_model(model)
    monkeypatch.setitem(ENGINES, "stub", _failing_voice_engine)
    start_runner()
    job_id = _queue_audio()
    failed = _wait_until_finished(job_id)

    monkeypatch.setitem(ENGINES, "stub", stub.from_config)
    queue.retry_job(job_id)

    assert (failed["stage"], failed["hint"]) == ("narrating", "Check the server.")
    assert _wait_until_finished(job_id)["state"] == "done"
    assert model.write_calls == 1


def test_paused_queue_picks_up_nothing_until_resumed(
    start_runner: StartRunner,
) -> None:
    queue.pause_queue()
    start_runner()
    job_id = _queue_audio()

    time.sleep(0.2)
    state_while_paused = _job(job_id)["state"]
    queue.resume_queue()

    assert state_while_paused == "queued"
    assert queue.is_queue_paused() is False
    assert _wait_until_finished(job_id)["state"] == "done"


def test_scripts_are_written_in_parallel(
    start_runner: StartRunner, use_script_model: UseScriptModel
) -> None:
    use_script_model(ParallelOnlyScriptModel())
    start_runner()

    job_ids = [_queue_audio(text) for text in ["One.", "Two."]]

    jobs = [_wait_until_finished(job_id) for job_id in job_ids]

    assert [job["state"] for job in jobs] == ["done", "done"], jobs


def test_wav_output_finishes_at_narration_with_format_and_size(
    start_runner: StartRunner,
) -> None:
    start_runner()

    job = _wait_until_finished(_queue_audio())

    audio = _audio_of(job)
    assert audio["path"] is not None
    assert (job["stage"], audio["format"], audio["conversion_note"]) == (
        "narrating",
        "wav",
        None,
    )
    assert audio["size_bytes"] == Path(audio["path"]).stat().st_size


def test_compressed_output_converts_and_deletes_the_wav(
    start_runner: StartRunner,
    use_ffmpeg: UseFfmpeg,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_FORMAT", "m4a")
    use_ffmpeg(FakeFfmpeg())
    start_runner()

    job = _wait_until_finished(_queue_audio())

    audio = _audio_of(job)
    assert job["state"] == "done", job["error"]
    assert audio["path"] is not None
    path = Path(audio["path"])
    assert (job["stage"], path.suffix, audio["format"]) == ("converting", ".m4a", "m4a")
    assert audio["size_bytes"] == path.stat().st_size
    assert audio["conversion_note"] is None
    assert not path.with_suffix(".wav").exists()


def test_missing_ffmpeg_finishes_with_the_wav_and_a_reason(
    start_runner: StartRunner,
    use_ffmpeg: UseFfmpeg,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_FORMAT", "mp3")
    use_ffmpeg(None)
    start_runner()

    job = _wait_until_finished(_queue_audio())

    audio = _audio_of(job)
    assert job["state"] == "done", job["error"]
    assert audio["path"] is not None and Path(audio["path"]).exists()
    assert audio["format"] == "wav"
    assert audio["conversion_note"] is not None
    assert "ffmpeg is not installed" in audio["conversion_note"]


def test_failed_conversion_keeps_the_wav_and_a_reason(
    start_runner: StartRunner,
    use_ffmpeg: UseFfmpeg,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_FORMAT", "m4a")
    use_ffmpeg(FakeFfmpeg(exit_code=187, stderr=b"Conversion failed!\n"))
    start_runner()

    job = _wait_until_finished(_queue_audio())

    audio = _audio_of(job)
    assert job["state"] == "done", job["error"]
    assert audio["path"] is not None and audio["path"].endswith(".wav")
    assert Path(audio["path"]).exists()
    assert audio["format"] == "wav"
    assert audio["conversion_note"] is not None
    assert "Conversion failed!" in audio["conversion_note"]


def test_conversion_finishing_after_a_cancel_keeps_only_the_wav(
    use_ffmpeg: UseFfmpeg, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_FORMAT", "m4a")
    use_ffmpeg(FakeFfmpeg())
    job_id = _queue_audio()
    assert runner.run_next("writing_script") and runner.run_next("narrating")
    claimed = job_store.claim_next("converting")
    assert claimed is not None

    queue.cancel_job(job_id)
    is_current = pipeline.convert(claimed)

    audio = _audio_of(_job(job_id))
    assert audio["path"] is not None
    wav_path = Path(audio["path"])
    assert is_current is False
    assert (wav_path.suffix, audio["format"]) == (".wav", "wav")
    assert wav_path.exists()
    assert not wav_path.with_suffix(".m4a").exists()
