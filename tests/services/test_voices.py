import pytest

from phemius.errors import InvalidInputError, VoiceError
from phemius.services import voices


@pytest.fixture
def kokoro_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_TTS", "kokoro")


@pytest.mark.usefixtures("kokoro_engine")
def test_bare_voice_is_namespaced_with_configured_engine() -> None:
    assert voices.resolve_voice("bf_emma") == "kokoro:bf_emma"


@pytest.mark.usefixtures("kokoro_engine")
def test_namespaced_voice_is_accepted() -> None:
    assert voices.resolve_voice("kokoro:bf_emma") == "kokoro:bf_emma"


def test_voice_from_another_engine_is_rejected() -> None:
    with pytest.raises(InvalidInputError) as raised:
        voices.resolve_voice("kokoro:af_heart")

    assert raised.value.field == "voice"


@pytest.mark.usefixtures("kokoro_engine")
def test_default_voice_is_engine_first_voice_when_unset() -> None:
    assert voices.resolve_voice() == "kokoro:af_heart"


@pytest.mark.usefixtures("kokoro_engine")
def test_bare_default_voice_from_env_is_namespaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_VOICE", "am_adam")

    assert voices.resolve_voice() == "kokoro:am_adam"


def test_invalid_default_voice_raises_with_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_VOICE", "af_heart")

    with pytest.raises(VoiceError) as raised:
        voices.resolve_voice()

    assert raised.value.hint == "Set PHEMIUS_VOICE to one of: stub:silent."


def test_unknown_engine_is_reported_not_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_TTS", "espeak")

    status = voices.check_engine()

    assert not status.is_ready
    assert status.hint is not None and "kokoro, stub" in status.hint
    assert voices.list_voices() == []
    assert voices.default_voice() is None


def test_default_piper_voice_is_the_cc0_voice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_TTS", "piper")

    assert voices.resolve_voice() == "piper:en_US-joe-medium"
