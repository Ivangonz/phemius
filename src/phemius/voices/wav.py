"""Join the audio parts of a long script into one WAV file with the stdlib.

Hosted engines are asked for WAV or raw PCM because uncompressed frames can be
concatenated without ffmpeg; the pipeline converts the result afterwards.
"""

import io
import wave
from dataclasses import dataclass
from pathlib import Path

from phemius.errors import VoiceError

MISMATCH_HINT = "Retry the job; if it fails again, choose another voice."
FRAMES_PER_READ = 1 << 16


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


def join_wav_files(paths: list[Path], out_path: Path) -> list[float]:
    """Write the WAV files back to back as `out_path`; each one's start in seconds.

    Frames are copied in blocks, so a long narration is never held in memory.
    Deletes `out_path` and raises `VoiceError` if a part is not WAV or its
    format differs from the first.
    """
    try:
        with wave.open(str(out_path), "wb") as out_file:
            return _copy_parts(paths, out_file)
    except (wave.Error, EOFError) as error:
        out_path.unlink(missing_ok=True)
        raise VoiceError(
            "A narrated section is not readable WAV audio.", MISMATCH_HINT
        ) from error
    except VoiceError:
        out_path.unlink(missing_ok=True)
        raise


def _copy_parts(paths: list[Path], out_file: wave.Wave_write) -> list[float]:
    starts: list[float] = []
    frames_written = 0
    audio_format: tuple[int, int, int] | None = None
    for path in paths:
        with wave.open(str(path), "rb") as part:
            part_format = (
                part.getnchannels(),
                part.getsampwidth(),
                part.getframerate(),
            )
            if audio_format is None:
                audio_format = part_format
                out_file.setparams(part.getparams())
            elif part_format != audio_format:
                raise VoiceError(
                    "The voice engine narrated sections in different audio formats.",
                    MISMATCH_HINT,
                )
            starts.append(frames_written / audio_format[2])
            frames_written += _copy_frames(part, out_file)
    return starts


def _copy_frames(part: wave.Wave_read, out_file: wave.Wave_write) -> int:
    copied = 0
    while frames := part.readframes(FRAMES_PER_READ):
        out_file.writeframesraw(frames)
        copied += len(frames) // (part.getnchannels() * part.getsampwidth())
    return copied
