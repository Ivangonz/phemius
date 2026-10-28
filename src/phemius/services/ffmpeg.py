"""Convert narrated WAV audio to M4A or MP3 with ffmpeg, which is optional.

Without ffmpeg, or when a conversion fails, the WAV is kept and the reason is
returned so the audio can show why it is WAV.
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import structlog

from phemius.store.jobs import AudioFormat

log = structlog.get_logger(__name__)

type CompressedFormat = Literal["m4a", "mp3"]
type CheckStatus = Literal["ok", "optional"]

CODEC_ARGUMENTS: dict[CompressedFormat, list[str]] = {
    "m4a": ["-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart"],
    "mp3": ["-c:a", "libmp3lame", "-b:a", "96k"],
}
# Speech at 96 kbps encodes far faster than real time; an hour of audio takes
# well under a minute, so this only catches a hung process.
CONVERT_TIMEOUT_SECONDS = 600
VERSION_TIMEOUT_SECONDS = 5
INSTALL_HINT = (
    "Install ffmpeg (for example `brew install ffmpeg` or `sudo apt install"
    " ffmpeg`) and restart Phemius, or choose WAV as the output format."
)


@dataclass(frozen=True)
class Conversion:
    path: Path
    format: AudioFormat
    # Why the audio stayed WAV, with a hint; None when it was converted.
    note: str | None = None


@dataclass(frozen=True)
class FfmpegCheck:
    is_present: bool
    version: str | None
    status: CheckStatus
    message: str
    hint: str | None = None


def find_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def run_ffmpeg(
    executable: str, arguments: list[str], timeout: float
) -> subprocess.CompletedProcess[bytes]:
    """Run ffmpeg without a shell, capturing its output."""
    return subprocess.run(
        [executable, *arguments], capture_output=True, timeout=timeout, check=False
    )


def check_ffmpeg() -> FfmpegCheck:
    """Whether ffmpeg is installed, and its version. Missing is fine: WAV is kept."""
    executable = find_ffmpeg()
    if executable is None:
        return _unusable(False, "ffmpeg is not installed; audio stays WAV.")
    try:
        result = run_ffmpeg(executable, ["-version"], VERSION_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return _unusable(True, "ffmpeg is installed but did not run.")
    if result.returncode != 0:
        return _unusable(True, "ffmpeg is installed but did not run.")
    version = _parse_version(result.stdout)
    name = f"ffmpeg {version}" if version else "ffmpeg"
    return FfmpegCheck(
        is_present=True,
        version=version,
        status="ok",
        message=f"{name} converts audio to M4A or MP3.",
    )


def _unusable(is_present: bool, message: str) -> FfmpegCheck:
    return FfmpegCheck(
        is_present=is_present,
        version=None,
        status="optional",
        message=message,
        hint=INSTALL_HINT,
    )


def convert(wav_path: Path, output_format: AudioFormat) -> Conversion:
    """Convert `wav_path` next to itself. The WAV is left for the caller to delete."""
    if output_format == "wav":
        return Conversion(wav_path, "wav")
    executable = find_ffmpeg()
    if executable is None:
        return _kept_wav(wav_path, "ffmpeg is not installed.", INSTALL_HINT)
    out_path = wav_path.with_suffix(f".{output_format}")
    reason = _encode(executable, wav_path, out_path, output_format)
    if reason is not None:
        out_path.unlink(missing_ok=True)
        return _kept_wav(wav_path, reason, "Check the ffmpeg install, or choose WAV.")
    return Conversion(out_path, output_format)


def _encode(
    executable: str, wav_path: Path, out_path: Path, output_format: CompressedFormat
) -> str | None:
    """Run the conversion. The failure reason, or None on success."""
    arguments = ["-y", "-loglevel", "error", "-i", str(wav_path)]
    arguments += [*CODEC_ARGUMENTS[output_format], str(out_path)]
    try:
        result = run_ffmpeg(executable, arguments, CONVERT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        log.warning("ffmpeg_timed_out", file=wav_path.name)
        return f"ffmpeg did not finish within {CONVERT_TIMEOUT_SECONDS} seconds."
    except OSError as error:
        log.warning("ffmpeg_not_started", error_type=type(error).__name__)
        return "ffmpeg could not be started."
    if result.returncode != 0:
        # stderr is kept off the logs: it repeats file paths and is long.
        log.warning("ffmpeg_failed", file=wav_path.name, exit_code=result.returncode)
        last_line = _last_line(result.stderr)
        return f"ffmpeg failed with exit code {result.returncode}: {last_line}"
    return None


def _kept_wav(wav_path: Path, reason: str, hint: str) -> Conversion:
    return Conversion(wav_path, "wav", f"Kept the WAV file: {reason} {hint}")


def _parse_version(stdout: bytes) -> str | None:
    """`7.1.1` from a first line such as `ffmpeg version 7.1.1 Copyright ...`."""
    words = stdout.decode(errors="replace").split()
    return words[2] if words[:2] == ["ffmpeg", "version"] and len(words) > 2 else None


def _last_line(stderr: bytes) -> str:
    lines = stderr.decode(errors="replace").strip().splitlines()
    return lines[-1][:200] if lines else "no error output."
