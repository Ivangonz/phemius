"""Writes silent WAV audio so the whole pipeline runs without a voice model."""

import wave
from pathlib import Path

from phemius.config import Config
from phemius.voices.base import Voice, VoiceCheck
from phemius.voices.text import split_chunks

SAMPLE_RATE = 16000
VOICES = [Voice(id="stub:silent", label="Silent (test engine)", accent=None)]


class StubEngine:
    extension = "wav"

    def voices(self) -> list[Voice]:
        return VOICES

    def check(self) -> VoiceCheck:
        return VoiceCheck(is_ready=True, message="The stub engine writes silence.")

    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        seconds = max(1, len(split_chunks(script)))
        with wave.open(str(out_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(b"\x00\x00" * SAMPLE_RATE * seconds)


def from_config(config: Config) -> StubEngine:
    return StubEngine()
