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


class WavJoiner:
    """Appends WAV files to `out_path` one at a time, recording where each starts.

    Frames are copied in blocks, so a long narration is never held in memory and
    each part can be deleted as soon as it is appended. On any error the output
    is deleted; a part that is not WAV, differs in format from the first, or
    cannot be written raises `VoiceError`.
    """

    def __init__(self, out_path: Path) -> None:
        self.out_path = out_path
        self.starts: list[float] = []
        self._frames = 0
        self._format: tuple[int, int, int] | None = None
        self._out: wave.Wave_write | None = None

    @property
    def duration_seconds(self) -> float:
        return self._frames / self._format[2] if self._format else 0.0

    def __enter__(self) -> "WavJoiner":
        return self

    def __exit__(self, error_type: type[BaseException] | None, *_: object) -> None:
        try:
            if self._out is not None:
                self._out.close()
        except (wave.Error, OSError) as error:
            self.out_path.unlink(missing_ok=True)
            if error_type is None:
                raise _write_error() from error
        if error_type is not None:
            self.out_path.unlink(missing_ok=True)

    def append(self, path: Path) -> None:
        try:
            with wave.open(str(path), "rb") as part:
                self._check_format(part)
                self.starts.append(self.duration_seconds)
                self._frames += _copy_frames(part, self._writer(part))
        except (wave.Error, EOFError) as error:
            raise VoiceError(
                "A narrated section is not readable WAV audio.", MISMATCH_HINT
            ) from error
        except OSError as error:
            raise _write_error() from error

    def _check_format(self, part: wave.Wave_read) -> None:
        part_format = (part.getnchannels(), part.getsampwidth(), part.getframerate())
        if self._format is None:
            self._format = part_format
        elif part_format != self._format:
            raise VoiceError(
                "The voice engine narrated sections in different audio formats.",
                MISMATCH_HINT,
            )

    def _writer(self, part: wave.Wave_read) -> wave.Wave_write:
        if self._out is None:
            self._out = wave.open(str(self.out_path), "wb")
            self._out.setparams(part.getparams())
        return self._out


def _write_error() -> VoiceError:
    return VoiceError(
        "The narrated audio could not be written.",
        "Check the free space and permissions of the data folder.",
    )


def _copy_frames(part: wave.Wave_read, out_file: wave.Wave_write) -> int:
    copied = 0
    while frames := part.readframes(FRAMES_PER_READ):
        out_file.writeframesraw(frames)
        copied += len(frames) // (part.getnchannels() * part.getsampwidth())
    return copied
