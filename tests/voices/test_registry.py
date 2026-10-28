import sys
from pathlib import Path

import pytest

from phemius.config import load_config
from phemius.errors import VoiceError
from phemius.voices import ENGINES, get_engine
from phemius.voices.kokoro import INSTALL_HINT, KokoroEngine


def test_unknown_engine_error_lists_valid_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_TTS", "espeak")

    with pytest.raises(VoiceError, match="espeak") as raised:
        get_engine(load_config())

    assert raised.value.hint == f"Set PHEMIUS_TTS to one of: {', '.join(ENGINES)}."


@pytest.mark.parametrize("name", list(ENGINES))
def test_every_engine_offers_voices_namespaced_with_its_name(name: str) -> None:
    engine = ENGINES[name](load_config())

    voice_ids = [voice.id for voice in engine.voices()]

    assert voice_ids
    assert all(voice_id.startswith(f"{name}:") for voice_id in voice_ids)


def test_missing_kokoro_reports_install_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "kokoro", None)

    status = KokoroEngine().check()

    assert not status.is_ready
    assert status.hint == INSTALL_HINT


def test_missing_kokoro_fails_synthesis_with_install_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "kokoro", None)

    with pytest.raises(VoiceError) as raised:
        KokoroEngine().synthesize("Hello.", tmp_path / "out.wav", "kokoro:af_heart")

    assert raised.value.hint == INSTALL_HINT
