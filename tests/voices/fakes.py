import hashlib
import io
import json
import struct
import threading
import wave
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx2

from phemius.errors import VoiceError
from phemius.voices import Voice, VoiceCheck
from phemius.voices.downloads import Fetch
from phemius.voices.piper import CatalogueVoice, VoiceFile
from phemius.voices.stub import StubEngine

type Handler = Callable[[httpx2.Request], httpx2.Response]
type UsePiper = Callable[[Fetch], Path]
"""Selects Piper with `fake_catalogue()`, fetching files with `fetch`."""

CONTENT = b"fake voice model"
VOICE = "piper:en_US-test-medium"
OTHER_VOICE = "piper:en_GB-other-low"
GATE_TIMEOUT_SECONDS = 5


class SynthesisCounter:
    """An engine with one voice that writes stub audio and records each call.

    With `error`, it writes a partial file and then raises it.
    """

    extension = "wav"

    def __init__(self, engine_name: str, error: VoiceError | None = None) -> None:
        self.voice_id = f"{engine_name}:one"
        self.error = error
        self.calls: list[str] = []

    def voices(self) -> list[Voice]:
        return [Voice(id=self.voice_id, label="One", accent=None)]

    def check(self) -> VoiceCheck:
        return VoiceCheck(True, "Ready.")

    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        # Kokoro's soundfile picks the format from the suffix, as real engines may.
        assert out_path.suffix == f".{self.extension}", out_path
        self.calls.append(script)
        if self.error is not None:
            out_path.write_bytes(b"partial")
            raise self.error
        StubEngine().synthesize(script, out_path, voice)


type UseCounter = Callable[..., SynthesisCounter]

LONG_SCRIPT = "\n\n".join(
    " ".join(f"Paragraph {para} explains step {step} in detail." for step in range(30))
    for para in range(30)
)


def wav_bytes(frame_count: int, sample_rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x01\x00" * frame_count)
    return buffer.getvalue()


def streamed_wav_bytes(frame_count: int) -> bytes:
    """A WAV whose header sizes are unknown, as servers that stream audio send it."""
    data = bytearray(wav_bytes(frame_count))
    unknown = struct.pack("<I", 0xFFFFFFFF)
    data[4:8] = unknown
    data[40:44] = unknown
    return bytes(data)


def read_wav(path: Path) -> tuple[int, int]:
    """The (sample rate, frame count) of a WAV file."""
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getframerate(), wav_file.getnframes()


def json_response(status: int, body: object) -> httpx2.Response:
    return httpx2.Response(status, content=json.dumps(body))


def recording(requests: list[httpx2.Request], respond: Handler) -> httpx2.MockTransport:
    def handle(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return respond(request)

    return httpx2.MockTransport(handle)


class GatedFetch:
    """Sends half of each file, then waits for `gate` before sending the rest.

    Only files whose URL passes `is_gated` wait; the rest arrive at once.
    """

    def __init__(
        self,
        gate: threading.Event,
        is_gated: Callable[[str], bool] = lambda url: True,
    ) -> None:
        self.gate = gate
        self.is_gated = is_gated
        self.urls: list[str] = []

    def __call__(self, url: str) -> Iterator[bytes]:
        self.urls.append(url)
        yield CONTENT[:4]
        if self.is_gated(url):
            self.gate.wait(GATE_TIMEOUT_SECONDS)
        yield CONTENT[4:]


def fake_fetch(url: str) -> Iterator[bytes]:
    yield CONTENT


def corrupt_fetch(url: str) -> Iterator[bytes]:
    yield b"x" * len(CONTENT)


def fake_catalogue() -> list[CatalogueVoice]:
    """Two Piper voices whose model and config are both `CONTENT`."""
    file = VoiceFile(hashlib.sha256(CONTENT).hexdigest(), len(CONTENT))
    return [
        CatalogueVoice(voice_id.split(":")[1], voice_id, "English", "CC0", file, file)
        for voice_id in (VOICE, OTHER_VOICE)
    ]
