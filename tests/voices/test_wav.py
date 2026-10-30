from pathlib import Path

import pytest

from phemius.errors import VoiceError
from phemius.voices.wav import join_wav_files
from tests.voices.fakes import read_wav, wav_bytes


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_joined_parts_start_where_the_previous_part_ends(tmp_path: Path) -> None:
    parts = [
        _write(tmp_path / f"{index}.wav", wav_bytes(frames, sample_rate=1000))
        for index, frames in enumerate([1500, 500, 2000])
    ]
    out_path = tmp_path / "joined.wav"

    starts = join_wav_files(parts, out_path)

    assert starts == [0.0, 1.5, 2.0]
    assert read_wav(out_path) == (1000, 4000)


def test_parts_in_different_formats_fail_and_leave_no_file(tmp_path: Path) -> None:
    parts = [
        _write(tmp_path / "a.wav", wav_bytes(100, sample_rate=24000)),
        _write(tmp_path / "b.wav", wav_bytes(100, sample_rate=22050)),
    ]
    out_path = tmp_path / "joined.wav"

    with pytest.raises(VoiceError) as raised:
        join_wav_files(parts, out_path)

    assert raised.value.hint
    assert not out_path.exists()


def test_a_part_that_is_not_wav_fails_with_a_voice_error(tmp_path: Path) -> None:
    parts = [
        _write(tmp_path / "a.wav", wav_bytes(100)),
        _write(tmp_path / "b.wav", b"ID3 not a wav file"),
    ]
    out_path = tmp_path / "joined.wav"

    with pytest.raises(VoiceError):
        join_wav_files(parts, out_path)

    assert not out_path.exists()
