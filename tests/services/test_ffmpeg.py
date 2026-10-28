import shutil
import subprocess
from pathlib import Path

import pytest

from phemius.services import ffmpeg
from tests.services.fakes import FakeFfmpeg, UseFfmpeg
from tests.voices.fakes import wav_bytes

IS_FFMPEG_INSTALLED = shutil.which("ffmpeg") is not None


@pytest.fixture
def wav_path(tmp_path: Path) -> Path:
    path = tmp_path / "7.wav"
    path.write_bytes(wav_bytes(frame_count=24000 * 5))
    return path


def test_wav_output_skips_ffmpeg(wav_path: Path, use_ffmpeg: UseFfmpeg) -> None:
    fake = use_ffmpeg(FakeFfmpeg())

    conversion = ffmpeg.convert(wav_path, "wav")

    assert (conversion.path, conversion.format, conversion.note) == (
        wav_path,
        "wav",
        None,
    )
    assert fake.calls == []


def test_conversion_writes_the_requested_format(
    wav_path: Path, use_ffmpeg: UseFfmpeg
) -> None:
    fake = use_ffmpeg(FakeFfmpeg())

    conversion = ffmpeg.convert(wav_path, "mp3")

    assert (conversion.path, conversion.format, conversion.note) == (
        wav_path.with_suffix(".mp3"),
        "mp3",
        None,
    )
    assert conversion.path.exists()
    assert wav_path.exists()
    assert "libmp3lame" in fake.calls[0]


def test_missing_ffmpeg_keeps_the_wav_with_an_install_hint(
    wav_path: Path, use_ffmpeg: UseFfmpeg
) -> None:
    use_ffmpeg(None)

    conversion = ffmpeg.convert(wav_path, "m4a")

    assert (conversion.path, conversion.format) == (wav_path, "wav")
    assert conversion.note is not None
    assert "ffmpeg is not installed" in conversion.note
    assert "Install ffmpeg" in conversion.note


def test_failed_conversion_keeps_the_wav_and_removes_partial_output(
    wav_path: Path, use_ffmpeg: UseFfmpeg
) -> None:
    use_ffmpeg(FakeFfmpeg(exit_code=1, stderr=b"noise\nUnknown encoder 'aac'\n"))

    conversion = ffmpeg.convert(wav_path, "m4a")

    assert (conversion.path, conversion.format) == (wav_path, "wav")
    assert conversion.note is not None
    assert "exit code 1" in conversion.note
    assert "Unknown encoder 'aac'" in conversion.note
    assert not wav_path.with_suffix(".m4a").exists()


def test_conversion_timeout_keeps_the_wav(
    wav_path: Path, use_ffmpeg: UseFfmpeg
) -> None:
    use_ffmpeg(FakeFfmpeg(error=subprocess.TimeoutExpired("ffmpeg", 1)))

    conversion = ffmpeg.convert(wav_path, "m4a")

    assert (conversion.path, conversion.format) == (wav_path, "wav")
    assert conversion.note is not None
    assert "did not finish" in conversion.note


def test_check_reports_version_when_installed(use_ffmpeg: UseFfmpeg) -> None:
    use_ffmpeg(FakeFfmpeg(stdout=b"ffmpeg version 7.1.1 Copyright (c) 2000-2025\n"))

    check = ffmpeg.check_ffmpeg()

    assert (check.is_present, check.version, check.status, check.hint) == (
        True,
        "7.1.1",
        "ok",
        None,
    )


def test_check_reports_missing_ffmpeg_as_optional(use_ffmpeg: UseFfmpeg) -> None:
    use_ffmpeg(None)

    check = ffmpeg.check_ffmpeg()

    assert (check.is_present, check.version, check.status) == (
        False,
        None,
        "optional",
    )
    assert check.hint is not None
    assert "Install ffmpeg" in check.hint


def test_check_reports_ffmpeg_that_does_not_run(use_ffmpeg: UseFfmpeg) -> None:
    use_ffmpeg(FakeFfmpeg(error=OSError("Exec format error")))

    check = ffmpeg.check_ffmpeg()

    assert (check.is_present, check.version, check.status) == (
        True,
        None,
        "optional",
    )
    assert check.hint is not None


@pytest.mark.ffmpeg
@pytest.mark.skipif(not IS_FFMPEG_INSTALLED, reason="ffmpeg is not installed")
@pytest.mark.parametrize("output_format", ["m4a", "mp3"])
def test_real_conversion_is_smaller_and_playable(
    wav_path: Path, output_format: ffmpeg.CompressedFormat
) -> None:
    conversion = ffmpeg.convert(wav_path, output_format)

    assert conversion.note is None, conversion.note
    assert conversion.format == output_format
    assert 0 < conversion.path.stat().st_size < wav_path.stat().st_size
    probe = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(conversion.path), "-f", "null", "-"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr
