import threading
import time
from collections.abc import Callable, Iterator

import pytest

from phemius.errors import NotFoundError, VoiceDownloadConflictError
from phemius.services import voice_downloads
from phemius.services.voice_downloads import DownloadProgress
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
