import hashlib
import sys
import threading
import time
import wave
from collections.abc import Callable, Iterator
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType

import pytest
from structlog.testing import capture_logs

from phemius.errors import VoiceError
from phemius.voices import piper
from phemius.voices.downloads import Fetch
from phemius.voices.piper import CatalogueVoice, PiperEngine, VoiceFile
from tests.voices.fakes import OTHER_VOICE, GatedFetch, fake_catalogue

MODEL_BYTES = b"fake onnx model"
CONFIG_BYTES = b'{"audio": {"sample_rate": 22050}}'
VOICE_ID = "piper:en_US-test-medium"
DEADLINE_SECONDS = 5


def _voice_file(content: bytes) -> VoiceFile:
    return VoiceFile(
        sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content)
    )


def _catalogue_voice(name: str) -> CatalogueVoice:
    return CatalogueVoice(
        name=name,
        label=name,
        accent="American English",
        license="CC0",
        model=_voice_file(MODEL_BYTES),
        config=_voice_file(CONFIG_BYTES),
    )


def fake_fetch(url: str) -> Iterator[bytes]:
    yield CONFIG_BYTES if url.endswith(".onnx.json") else MODEL_BYTES


def corrupt_fetch(url: str) -> Iterator[bytes]:
    yield b"x" * 4


def broken_fetch(url: str) -> Iterator[bytes]:
    yield b"partial"
    raise OSError("connection reset")


class FakePiperVoice:
    @staticmethod
    def load(model_path: str) -> "FakePiperVoice":
        assert Path(model_path).exists()
        return FakePiperVoice()

    def synthesize_wav(self, text: str, wav_file: wave.Wave_write) -> None:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x01\x00" * len(text))


@pytest.fixture(autouse=True)
def test_catalogue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        piper,
        "CATALOGUE",
        [_catalogue_voice("en_US-test-medium"), _catalogue_voice("en_GB-other-low")],
    )


@pytest.fixture
def piper_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("piper")
    module.__spec__ = ModuleSpec("piper", None)
    setattr(module, "PiperVoice", FakePiperVoice)
    monkeypatch.setitem(sys.modules, "piper", module)


@pytest.fixture
def piper_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "piper", None)


@pytest.fixture
def voices_dir(tmp_path: Path) -> Path:
    return tmp_path / "voices"


@pytest.fixture
def make_engine(voices_dir: Path) -> Callable[..., PiperEngine]:
    def make(fetch: Fetch = fake_fetch) -> PiperEngine:
        return PiperEngine(voices_dir=voices_dir, fetch=fetch)

    return make


def test_download_writes_verified_files_and_reports_progress(
    make_engine: Callable[..., PiperEngine],
) -> None:
    progress: list[tuple[int, int]] = []
    total = len(MODEL_BYTES) + len(CONFIG_BYTES)

    model_path = make_engine().download(
        VOICE_ID, lambda done, size: progress.append((done, size))
    )

    assert model_path.read_bytes() == MODEL_BYTES
    assert model_path.with_suffix(".onnx.json").read_bytes() == CONFIG_BYTES
    assert progress[-1] == (total, total)


@pytest.mark.parametrize("fetch", [corrupt_fetch, broken_fetch])
def test_failed_download_raises_and_leaves_no_partial_file(
    make_engine: Callable[..., PiperEngine],
    voices_dir: Path,
    fetch: Fetch,
) -> None:
    with pytest.raises(VoiceError) as raised:
        make_engine(fetch).download(VOICE_ID)

    assert raised.value.hint
    assert list(voices_dir.iterdir()) == []


def test_voices_mark_installed_and_downloadable_with_sizes(
    make_engine: Callable[..., PiperEngine],
) -> None:
    engine = make_engine()
    engine.download(VOICE_ID)

    voices = {voice.id: voice for voice in engine.voices()}

    assert voices[VOICE_ID].is_installed
    assert not voices["piper:en_GB-other-low"].is_installed
    assert voices["piper:en_GB-other-low"].size_bytes == len(MODEL_BYTES) + len(
        CONFIG_BYTES
    )


@pytest.mark.usefixtures("piper_missing")
def test_check_reports_not_installed(make_engine: Callable[..., PiperEngine]) -> None:
    status = make_engine().check()

    assert not status.is_ready
    assert status.hint == piper.INSTALL_HINT


@pytest.mark.usefixtures("piper_installed")
def test_check_reports_voice_not_downloaded_then_ready(
    make_engine: Callable[..., PiperEngine],
) -> None:
    engine = make_engine()
    before = engine.check()
    engine.download(VOICE_ID)
    after = engine.check()

    assert "not downloaded" in before.message
    assert after.message == "Piper is ready."


@pytest.mark.usefixtures("piper_installed")
def test_synthesize_downloads_the_voice_on_demand_without_kokoro(
    make_engine: Callable[..., PiperEngine],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "kokoro", None)
    out_path = tmp_path / "out.wav"

    make_engine().synthesize("Hello there.", out_path, VOICE_ID)

    with wave.open(str(out_path), "rb") as wav_file:
        assert wav_file.getnframes() == len("Hello there.")


@pytest.mark.usefixtures("piper_missing")
def test_missing_piper_fails_synthesis_with_install_hint(
    make_engine: Callable[..., PiperEngine], tmp_path: Path
) -> None:
    with pytest.raises(VoiceError) as raised:
        make_engine().synthesize("Hello.", tmp_path / "out.wav", VOICE_ID)

    assert raised.value.hint == piper.INSTALL_HINT


SCRIPT = "A sentence the phonemizer cannot read."


def _fail_before_writing(text: str, wav_file: wave.Wave_write) -> None:
    raise RuntimeError(f"Failed to phonemize sentence: {text}")


def _fail_after_writing(text: str, wav_file: wave.Wave_write) -> None:
    wav_file.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
    wav_file.writeframes(b"\x01\x00" * 100)
    raise ValueError(f"Bad phoneme in: {text}")


def _write_nothing(text: str, wav_file: wave.Wave_write) -> None:
    pass


def _fail_to_write(text: str, wav_file: wave.Wave_write) -> None:
    raise OSError(28, f"No space left on device while writing {text}")


@pytest.mark.usefixtures("piper_installed")
@pytest.mark.parametrize(
    ("synthesize_wav", "message", "hint"),
    [
        (_fail_before_writing, "(RuntimeError)", piper.SYNTHESIS_HINT),
        (_fail_after_writing, "(ValueError)", piper.SYNTHESIS_HINT),
        (_write_nothing, "produced no audio", piper.SYNTHESIS_HINT),
        (_fail_to_write, "could not be written", "free space and permissions"),
    ],
)
def test_piper_failure_raises_voice_error_without_the_script(
    synthesize_wav: Callable[[str, wave.Wave_write], None],
    message: str,
    hint: str,
    make_engine: Callable[..., PiperEngine],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        FakePiperVoice,
        "synthesize_wav",
        lambda voice, text, wav_file: synthesize_wav(text, wav_file),
    )

    with pytest.raises(VoiceError) as raised:
        make_engine().synthesize(SCRIPT, tmp_path / "out.wav", VOICE_ID)

    assert message in raised.value.message
    assert raised.value.hint and hint in raised.value.hint
    assert SCRIPT not in raised.value.message + raised.value.hint


@pytest.mark.usefixtures("piper_installed")
def test_piper_failure_logs_where_it_failed_but_not_the_script(
    make_engine: Callable[..., PiperEngine],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        FakePiperVoice,
        "synthesize_wav",
        lambda voice, text, wav_file: _fail_before_writing(text, wav_file),
    )

    with capture_logs() as logs, pytest.raises(VoiceError):
        make_engine().synthesize(SCRIPT, tmp_path / "out.wav", VOICE_ID)

    [failure] = [entry for entry in logs if entry["event"] == "piper_synthesis_failed"]
    assert failure["error_type"] == "RuntimeError"
    assert failure["module"] == __name__
    assert isinstance(failure["line"], int)
    assert SCRIPT not in str(logs)


def _start_download(engine: PiperEngine, voice: str) -> threading.Thread:
    thread = threading.Thread(target=engine.download, args=(voice,))
    thread.start()
    return thread


def test_concurrent_downloads_of_one_voice_fetch_each_file_once(
    voices_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(piper, "CATALOGUE", fake_catalogue())
    release, is_waiting = threading.Event(), threading.Event()
    fetch = GatedFetch(release)
    engine = PiperEngine(voices_dir, fetch=fetch)
    first = _start_download(engine, VOICE_ID)
    deadline = time.monotonic() + DEADLINE_SECONDS
    while not fetch.urls:
        assert time.monotonic() < deadline, "the first download never started"
        time.sleep(0.01)

    def on_progress(done: int, total: int) -> None:
        if done == 0:  # reported only while queued behind the first download
            is_waiting.set()

    second = threading.Thread(target=engine.download, args=(VOICE_ID, on_progress))
    second.start()
    assert is_waiting.wait(DEADLINE_SECONDS)
    release.set()
    first.join(DEADLINE_SECONDS)
    second.join(DEADLINE_SECONDS)

    assert len(fetch.urls) == 2


def test_downloads_of_different_voices_do_not_wait_on_each_other(
    voices_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(piper, "CATALOGUE", fake_catalogue())
    release = threading.Event()
    engine = PiperEngine(voices_dir, GatedFetch(release, lambda url: "test" in url))
    first = _start_download(engine, VOICE_ID)
    other = _start_download(engine, OTHER_VOICE)

    other.join(DEADLINE_SECONDS / 2)
    is_other_done = not other.is_alive()
    release.set()
    first.join(DEADLINE_SECONDS)

    assert is_other_done
