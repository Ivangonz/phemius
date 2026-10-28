import json
import logging
from pathlib import Path

import httpx2
import pytest
from structlog.testing import capture_logs

from phemius.config import load_config
from phemius.errors import VoiceError
from phemius.voices.openai_speech import MAX_CHARS, OpenAISpeechEngine, from_config
from tests.voices.fakes import (
    LONG_SCRIPT,
    Handler,
    json_response,
    read_wav,
    recording,
    streamed_wav_bytes,
    wav_bytes,
)

SECRET = "sk-speech-secret"
VOICE = "openai_speech:nova"


def _engine(
    respond: Handler,
    requests: list[httpx2.Request] | None = None,
    api_key: str | None = SECRET,
) -> OpenAISpeechEngine:
    return OpenAISpeechEngine(
        base_url="http://speech.local/v1",
        api_key=api_key,
        model="tts-1",
        voice_names=["nova", "onyx"],
        transport=recording([] if requests is None else requests, respond),
    )


def test_long_script_is_split_under_the_limit_and_joined_into_one_wav(
    tmp_path: Path,
) -> None:
    requests: list[httpx2.Request] = []
    engine = _engine(
        lambda request: httpx2.Response(200, content=wav_bytes(100)), requests
    )
    out_path = tmp_path / "out.wav"

    engine.synthesize(LONG_SCRIPT, out_path, VOICE)

    inputs = [json.loads(request.content)["input"] for request in requests]
    assert len(LONG_SCRIPT) > MAX_CHARS and len(inputs) > 1
    assert all(len(text) <= MAX_CHARS for text in inputs)
    assert " ".join(inputs).split() == LONG_SCRIPT.split()
    assert read_wav(out_path) == (24000, 100 * len(inputs))


def test_request_asks_for_wav_with_model_voice_and_bearer_key(tmp_path: Path) -> None:
    requests: list[httpx2.Request] = []
    engine = _engine(
        lambda request: httpx2.Response(200, content=wav_bytes(10)), requests
    )

    engine.synthesize("Hello there.", tmp_path / "out.wav", VOICE)

    (request,) = requests
    assert request.url == "http://speech.local/v1/audio/speech"
    assert request.headers["authorization"] == f"Bearer {SECRET}"
    assert json.loads(request.content) == {
        "model": "tts-1",
        "voice": "nova",
        "input": "Hello there.",
        "response_format": "wav",
    }


def test_server_without_key_gets_no_authorization_header(tmp_path: Path) -> None:
    requests: list[httpx2.Request] = []
    engine = _engine(
        lambda request: httpx2.Response(200, content=wav_bytes(10)), requests, None
    )

    engine.synthesize("Hello there.", tmp_path / "out.wav", VOICE)

    assert "authorization" not in requests[0].headers


def test_streamed_wav_parts_are_joined(tmp_path: Path) -> None:
    engine = _engine(
        lambda request: httpx2.Response(200, content=streamed_wav_bytes(50))
    )
    out_path = tmp_path / "out.wav"

    engine.synthesize(LONG_SCRIPT, out_path, VOICE)

    sample_rate, frame_count = read_wav(out_path)
    assert frame_count > 50 and frame_count % 50 == 0


@pytest.mark.parametrize(
    ("status", "body", "hint_word"),
    [
        (401, {"error": {"message": f"Incorrect API key {SECRET}"}}, "API_KEY"),
        (429, {"error": {"code": "insufficient_quota"}}, "billing"),
        (429, {"error": {"code": "rate_limit_exceeded"}}, "rate limiting"),
        (404, {"error": {"message": "Not found"}}, "BASE_URL"),
    ],
)
def test_provider_errors_map_to_voice_error_with_hint(
    tmp_path: Path, status: int, body: object, hint_word: str
) -> None:
    engine = _engine(lambda request: json_response(status, body))

    with pytest.raises(VoiceError) as raised:
        engine.synthesize("Hello.", tmp_path / "out.wav", VOICE)

    assert raised.value.message == f"The speech server returned {status}."
    assert raised.value.hint is not None and hint_word in raised.value.hint
    assert SECRET not in str(raised.value)


def test_unreachable_server_raises_with_base_url_hint(tmp_path: Path) -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused", request=request)

    with pytest.raises(VoiceError) as raised:
        _engine(refuse).synthesize("Hello.", tmp_path / "out.wav", VOICE)

    assert raised.value.hint is not None and "BASE_URL" in raised.value.hint


def test_parts_with_different_formats_are_rejected(tmp_path: Path) -> None:
    rates = iter([24000, 22050, 24000, 22050] * 10)
    engine = _engine(
        lambda request: httpx2.Response(200, content=wav_bytes(10, next(rates)))
    )

    with pytest.raises(VoiceError, match="different audio formats"):
        engine.synthesize(LONG_SCRIPT, tmp_path / "out.wav", VOICE)


def test_non_wav_reply_raises_with_hint(tmp_path: Path) -> None:
    engine = _engine(lambda request: httpx2.Response(200, content=b"ID3 mp3 data"))

    with pytest.raises(VoiceError) as raised:
        engine.synthesize("Hello.", tmp_path / "out.wav", VOICE)

    assert raised.value.hint is not None and "wav" in raised.value.hint


def test_check_is_ready_when_the_server_answers() -> None:
    requests: list[httpx2.Request] = []
    engine = _engine(lambda request: json_response(200, {"data": []}), requests)

    status = engine.check()

    assert status.is_ready
    assert requests[0].url == "http://speech.local/v1/models"


def test_check_reports_a_bad_key_with_hint() -> None:
    engine = _engine(lambda request: json_response(401, {"error": {}}))

    status = engine.check()

    assert not status.is_ready
    assert status.hint is not None and "API_KEY" in status.hint


def test_key_never_appears_in_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    failing = _engine(lambda request: json_response(401, {"error": {"key": SECRET}}))
    working = _engine(lambda request: httpx2.Response(200, content=wav_bytes(10)))

    with capture_logs() as logs:
        working.synthesize("Hello.", tmp_path / "out.wav", VOICE)
        with pytest.raises(VoiceError):
            failing.synthesize("Hello.", tmp_path / "out.wav", VOICE)

    assert logs
    assert SECRET not in str(logs)
    assert SECRET not in caplog.text


def test_from_config_reads_voices_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_OPENAI_SPEECH_VOICES", "nova, onyx")
    monkeypatch.setenv("PHEMIUS_OPENAI_SPEECH_API_KEY", SECRET)

    engine = from_config(load_config())

    assert [voice.id for voice in engine.voices()] == [
        "openai_speech:nova",
        "openai_speech:onyx",
    ]
