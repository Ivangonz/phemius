import hashlib
import io
import json
import struct
import threading
import wave
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx2

from phemius.voices.downloads import Fetch
from phemius.voices.piper import CatalogueVoice, VoiceFile

type Handler = Callable[[httpx2.Request], httpx2.Response]
type UsePiper = Callable[[Fetch], Path]
"""Selects Piper with `fake_catalogue()`, fetching files with `fetch`."""

CONTENT = b"fake voice model"
VOICE = "piper:en_US-test-medium"
OTHER_VOICE = "piper:en_GB-other-low"
GATE_TIMEOUT_SECONDS = 5

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
    """Sends half of each file, then waits for `gate` before sending the rest."""

    def __init__(self, gate: threading.Event) -> None:
        self.gate = gate
        self.urls: list[str] = []

    def __call__(self, url: str) -> Iterator[bytes]:
        self.urls.append(url)
        yield CONTENT[:4]
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
