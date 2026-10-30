from pathlib import Path

import pytest

from phemius.errors import VoiceError
from phemius.voices.wav import WavJoiner
from tests.voices.fakes import read_wav, wav_bytes


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def _join(parts: list[Path], out_path: Path) -> WavJoiner:
    with WavJoiner(out_path) as joiner:
        for part in parts:
            joiner.append(part)
    return joiner


def test_joined_parts_start_where_the_previous_part_ends(tmp_path: Path) -> None:
    parts = [
        _write(tmp_path / f"{index}.wav", wav_bytes(frames, sample_rate=1000))
        for index, frames in enumerate([1500, 500, 2000])
    ]
    out_path = tmp_path / "joined.wav"

    joiner = _join(parts, out_path)

    assert (joiner.starts, joiner.duration_seconds) == ([0.0, 1.5, 2.0], 4.0)
    assert read_wav(out_path) == (1000, 4000)


def test_parts_in_different_formats_fail_and_leave_no_file(tmp_path: Path) -> None:
    parts = [
        _write(tmp_path / "a.wav", wav_bytes(100, sample_rate=24000)),
        _write(tmp_path / "b.wav", wav_bytes(100, sample_rate=22050)),
    ]
    out_path = tmp_path / "joined.wav"

    with pytest.raises(VoiceError) as raised:
        _join(parts, out_path)

    assert raised.value.hint
    assert not out_path.exists()


@pytest.mark.parametrize("first_is_valid", [True, False])
def test_a_part_that_is_not_wav_fails_with_a_voice_error(
    tmp_path: Path, first_is_valid: bool
) -> None:
    valid = _write(tmp_path / "a.wav", wav_bytes(100))
    invalid = _write(tmp_path / "b.wav", b"ID3 not a wav file")
    out_path = tmp_path / "joined.wav"

    with pytest.raises(VoiceError):
        _join([valid, invalid] if first_is_valid else [invalid, valid], out_path)

    assert not out_path.exists()


def test_a_part_that_cannot_be_read_fails_with_a_hint(tmp_path: Path) -> None:
    parts = [_write(tmp_path / "a.wav", wav_bytes(100)), tmp_path / "missing.wav"]
    out_path = tmp_path / "joined.wav"

    with pytest.raises(VoiceError) as raised:
        _join(parts, out_path)

    assert raised.value.hint
    assert not out_path.exists()
