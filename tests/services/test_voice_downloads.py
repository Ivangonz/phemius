import threading
import time
from collections.abc import Callable, Iterator

import pytest

from phemius.config import load_config
from phemius.errors import NotFoundError, VoiceDownloadConflictError
from phemius.services import voice_downloads, voices
from phemius.services.voice_downloads import DownloadProgress
from phemius.voices import get_engine
from phemius.voices.piper import PiperEngine
from tests.voices.fakes import (
    CONTENT,
    OTHER_VOICE,
    VOICE,
    GatedFetch,
    UsePiper,
    corrupt_fetch,
    fake_fetch,
)

DEADLINE_SECONDS = 5


def wait_until(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + DEADLINE_SECONDS
    while not condition():
        assert time.monotonic() < deadline, "the condition never held"
        time.sleep(0.01)


def configured_piper() -> PiperEngine:
    engine = get_engine(load_config())
    assert isinstance(engine, PiperEngine)
    return engine


def wait_for_progress(
    voice: str, is_done: Callable[[DownloadProgress], bool]
) -> DownloadProgress:
    deadline = time.monotonic() + DEADLINE_SECONDS
    while time.monotonic() < deadline:
        progress = voice_downloads.download_progress(voice)
        if progress is not None and is_done(progress):
            return progress
        time.sleep(0.01)
    raise AssertionError(f"Download never reached the expected state: {progress}")


@pytest.fixture(autouse=True)
def running_downloads() -> Iterator[None]:
    voice_downloads.start_downloads()
    yield
    voice_downloads.stop_downloads()


def test_download_reports_progress_and_ends_installed(use_piper: UsePiper) -> None:
    voices_dir = use_piper(fake_fetch)

    started = voice_downloads.download_voice(VOICE)

    finished = wait_for_progress(
        VOICE, lambda progress: progress.state != "downloading"
    )
    assert (started.state, started.done) == ("downloading", 0)
    assert finished.state == "installed"
    assert finished.done == finished.total == 2 * len(CONTENT)
    assert (voices_dir / "en_US-test-medium.onnx").read_bytes() == CONTENT


def test_hash_mismatch_fails_with_a_hint_and_leaves_no_file(
    use_piper: UsePiper,
) -> None:
    voices_dir = use_piper(corrupt_fetch)

    voice_downloads.download_voice(VOICE)

    failed = wait_for_progress(VOICE, lambda progress: progress.state == "failed")
    assert failed.message and failed.hint
    assert list(voices_dir.iterdir()) == []


def test_second_request_while_downloading_returns_the_same_download(
    use_piper: UsePiper,
) -> None:
    release = threading.Event()
    fetch = GatedFetch(release)
    use_piper(fetch)

    voice_downloads.download_voice(VOICE)
    wait_for_progress(VOICE, lambda progress: progress.done > 0)
    again = voice_downloads.download_voice(VOICE)
    release.set()

    assert again.state == "downloading"
    wait_for_progress(VOICE, lambda progress: progress.state == "installed")
    assert len(fetch.urls) == 2  # the config and the model, once each


def test_another_voice_waits_for_the_running_download(use_piper: UsePiper) -> None:
    release = threading.Event()
    use_piper(GatedFetch(release))
    voice_downloads.download_voice(VOICE)

    with pytest.raises(VoiceDownloadConflictError) as raised:
        voice_downloads.download_voice(OTHER_VOICE)

    release.set()
    assert raised.value.hint
    wait_for_progress(VOICE, lambda progress: progress.state == "installed")


def test_stopping_mid_download_joins_the_thread_and_leaves_no_file(
    use_piper: UsePiper,
) -> None:
    voices_dir = use_piper(GatedFetch(voice_downloads.stop_signal()))
    voice_downloads.download_voice(VOICE)
    wait_for_progress(VOICE, lambda progress: progress.done > 0)

    voice_downloads.stop_downloads()

    threads = [thread.name for thread in threading.enumerate()]
    assert "voice-download" not in threads
    assert voice_downloads.download_progress(VOICE) is None
    assert list(voices_dir.iterdir()) == []


def test_an_installed_voice_is_not_downloaded_again(use_piper: UsePiper) -> None:
    fetch = GatedFetch(threading.Event())
    use_piper(fake_fetch)
    voice_downloads.download_voice(VOICE)
    wait_for_progress(VOICE, lambda progress: progress.state == "installed")
    use_piper(fetch)

    assert voice_downloads.download_voice(VOICE).state == "installed"
    assert fetch.urls == []


def test_engine_without_downloads_is_a_conflict_with_a_hint() -> None:
    with pytest.raises(VoiceDownloadConflictError) as raised:
        voice_downloads.download_voice("stub:silent")

    assert raised.value.status_code == 409
    assert raised.value.hint


@pytest.mark.parametrize(
    "voice", ["piper:missing", "piper:../../etc/passwd", "kokoro:af_heart"]
)
def test_voice_outside_the_catalogue_is_not_found(
    use_piper: UsePiper, voice: str
) -> None:
    use_piper(fake_fetch)

    with pytest.raises(NotFoundError):
        voice_downloads.download_voice(voice)


def test_a_failure_is_hidden_once_the_voice_is_installed_another_way(
    use_piper: UsePiper,
) -> None:
    use_piper(corrupt_fetch)
    voice_downloads.download_voice(VOICE)
    wait_for_progress(VOICE, lambda progress: progress.state == "failed")
    use_piper(fake_fetch)

    configured_piper().download(VOICE)  # as a narration does on first use

    views, _ = voices.list_voice_views("default", 25, 0)
    view = next(view for view in views if view.id == VOICE)
    assert view.is_installed is True
    assert view.download is None
    assert voice_downloads.download_voice(VOICE).state == "installed"
    assert voice_downloads.download_progress(VOICE) is None


def test_stopping_while_queued_behind_narration_ends_promptly(
    use_piper: UsePiper,
) -> None:
    release = threading.Event()
    fetch = GatedFetch(release)
    use_piper(fetch)
    narration = threading.Thread(target=configured_piper().download, args=(VOICE,))
    narration.start()
    wait_until(lambda: len(fetch.urls) > 0)
    voice_downloads.download_voice(VOICE)

    started = time.monotonic()
    voice_downloads.stop_downloads()
    stop_seconds = time.monotonic() - started
    voice_downloads.start_downloads()
    release.set()
    narration.join(DEADLINE_SECONDS)

    assert stop_seconds < voice_downloads.STOP_TIMEOUT_SECONDS
    assert voice_downloads.THREAD_NAME not in [t.name for t in threading.enumerate()]
    assert voice_downloads.download_voice(OTHER_VOICE).state == "downloading"
    wait_for_progress(OTHER_VOICE, lambda progress: progress.state == "installed")


def test_stopping_during_the_model_keeps_only_the_verified_config(
    use_piper: UsePiper,
) -> None:
    is_model = GatedFetch(
        voice_downloads.stop_signal(), lambda url: url.endswith(".onnx")
    )
    voices_dir = use_piper(is_model)
    voice_downloads.download_voice(VOICE)
    wait_for_progress(VOICE, lambda progress: progress.done > len(CONTENT))

    voice_downloads.stop_downloads()

    assert [path.name for path in voices_dir.iterdir()] == [
        "en_US-test-medium.onnx.json"
    ]
