"""Writes silent WAV audio so the whole pipeline runs without a voice model."""

import wave
from pathlib import Path

from phemius.voices.text import split_chunks

SAMPLE_RATE = 16000


class StubEngine:
    extension = "wav"

    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        seconds = max(1, len(split_chunks(script)))
        with wave.open(str(out_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(b"\x00\x00" * SAMPLE_RATE * seconds)
