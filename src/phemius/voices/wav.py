"""Join the audio parts of a long script into one WAV file with the stdlib.

Hosted engines are asked for WAV or raw PCM because uncompressed frames can be
concatenated without ffmpeg; the pipeline converts the result afterwards.
"""

import io
import wave
from dataclasses import dataclass
from pathlib import Path

from phemius.errors import VoiceError


@dataclass(frozen=True)
class Clip:
    channels: int
    sample_width: int
    sample_rate: int
    frames: bytes

    @property
    def audio_format(self) -> tuple[int, int, int]:
        return self.channels, self.sample_width, self.sample_rate


def read_wav(data: bytes, hint: str) -> Clip:
    """Parse WAV bytes. Streamed WAVs with unknown header sizes read to the end."""
    try:
        with wave.open(io.BytesIO(data), "rb") as wav_file:
            return Clip(
                channels=wav_file.getnchannels(),
                sample_width=wav_file.getsampwidth(),
                sample_rate=wav_file.getframerate(),
                frames=wav_file.readframes(wav_file.getnframes()),
            )
    except (wave.Error, EOFError) as error:
        raise VoiceError("The voice engine did not return WAV audio.", hint) from error


def wav_duration_seconds(path: Path) -> float | None:
    """The length of a WAV file from its header, or None if it cannot be read."""
    try:
        with wave.open(str(path), "rb") as wav_file:
            return wav_file.getnframes() / wav_file.getframerate()
    except (wave.Error, EOFError, ZeroDivisionError):
        return None


def write_clips(clips: list[Clip], out_path: Path) -> None:
    """Write `clips` back to back as one WAV file."""
    if not any(clip.frames for clip in clips):
        raise VoiceError("The voice engine returned no audio for this script.")
    audio_format = clips[0].audio_format
    if any(clip.audio_format != audio_format for clip in clips):
        raise VoiceError("The voice engine returned parts in different audio formats.")
    channels, sample_width, sample_rate = audio_format
    with wave.open(str(out_path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        for clip in clips:
            wav_file.writeframes(clip.frames)
