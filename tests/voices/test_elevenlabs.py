import json
import logging
from pathlib import Path

import httpx2
import pytest
from structlog.testing import capture_logs

from phemius.config import load_config
from phemius.errors import VoiceError
from phemius.voices.elevenlabs import (
    MAX_CHARS,
    SAMPLE_RATE,
    ElevenLabsEngine,
    from_config,
)
from tests.voices.fakes import LONG_SCRIPT, Handler, json_response, read_wav, recording

SECRET = "el-secret-key"
VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"
VOICE = f"elevenlabs:{VOICE_ID}"


def _pcm(frame_count: int) -> httpx2.Response:
    return httpx2.Response(200, content=b"\x01\x00" * frame_count)


def _engine(
    respond: Handler,
    requests: list[httpx2.Request] | None = None,
    api_key: str | None = SECRET,
) -> ElevenLabsEngine:
    return ElevenLabsEngine(
        api_key=api_key,
        voice_ids=[VOICE_ID],
        transport=recording([] if requests is None else requests, respond),
    )


def test_long_script_is_split_under_the_limit_and_joined_into_one_wav(
    tmp_path: Path,
) -> None:
    requests: list[httpx2.Request] = []
    engine = _engine(lambda request: _pcm(100), requests)
    out_path = tmp_path / "out.wav"

    engine.synthesize(LONG_SCRIPT, out_path, VOICE)

    texts = [json.loads(request.content)["text"] for request in requests]
    assert len(LONG_SCRIPT) > MAX_CHARS and len(texts) > 1
    assert all(len(text) <= MAX_CHARS for text in texts)
    assert " ".join(texts).split() == LONG_SCRIPT.split()
    assert read_wav(out_path) == (SAMPLE_RATE, 100 * len(texts))


def test_request_asks_for_pcm_for_the_voice_with_the_key(tmp_path: Path) -> None:
    requests: list[httpx2.Request] = []
    engine = _engine(lambda request: _pcm(10), requests)

    engine.synthesize("Hello there.", tmp_path / "out.wav", VOICE)

    (request,) = requests
    assert request.url.path == f"/v1/text-to-speech/{VOICE_ID}"
    assert request.url.params["output_format"] == f"pcm_{SAMPLE_RATE}"
    assert request.headers["xi-api-key"] == SECRET


@pytest.mark.parametrize(
    ("status", "body", "hint_word"),
    [
        (401, {"detail": {"status": "invalid_api_key"}}, "ELEVENLABS_API_KEY"),
        (401, {"detail": {"status": "quota_exceeded"}}, "credits"),
        (429, {"detail": {"status": "too_many_concurrent_requests"}}, "rate"),
        (404, {"detail": {"status": "voice_not_found"}}, "PHEMIUS_ELEVENLABS_VOICES"),
    ],
)
def test_provider_errors_map_to_voice_error_with_hint(
    tmp_path: Path, status: int, body: object, hint_word: str
) -> None:
    engine = _engine(lambda request: json_response(status, body))

    with pytest.raises(VoiceError) as raised:
        engine.synthesize("Hello.", tmp_path / "out.wav", VOICE)

    assert raised.value.message == f"ElevenLabs returned {status}."
    assert raised.value.hint is not None and hint_word in raised.value.hint


def test_missing_key_is_not_ready_and_fails_synthesis(tmp_path: Path) -> None:
    requests: list[httpx2.Request] = []
    engine = _engine(lambda request: _pcm(10), requests, api_key=None)

    status = engine.check()
    with pytest.raises(VoiceError) as raised:
        engine.synthesize("Hello.", tmp_path / "out.wav", VOICE)

    assert not status.is_ready
    assert status.hint is not None and "ELEVENLABS_API_KEY" in status.hint
    assert raised.value.hint == status.hint
    assert requests == []


def test_check_is_ready_when_the_first_voice_is_found() -> None:
    requests: list[httpx2.Request] = []
    engine = _engine(
        lambda request: json_response(200, {"voice_id": VOICE_ID}), requests
    )

    status = engine.check()

    assert status.is_ready
    assert requests[0].url.path == f"/v1/voices/{VOICE_ID}"


def test_check_reports_quota_with_hint() -> None:
    body = {"detail": {"status": "quota_exceeded"}}
    engine = _engine(lambda request: json_response(401, body))

    status = engine.check()

    assert not status.is_ready
    assert status.hint is not None and "credits" in status.hint


def test_key_never_appears_in_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    body = {"detail": {"status": "invalid_api_key", "message": SECRET}}
    failing = _engine(lambda request: json_response(401, body))
    working = _engine(lambda request: _pcm(10))

    with capture_logs() as logs:
        working.synthesize("Hello.", tmp_path / "out.wav", VOICE)
        with pytest.raises(VoiceError) as raised:
            failing.synthesize("Hello.", tmp_path / "out.wav", VOICE)

    assert logs
    assert SECRET not in str(logs)
    assert SECRET not in caplog.text
    assert SECRET not in str(raised.value)


def test_from_config_reads_voice_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_ELEVENLABS_VOICES", "abc123,def456")

    engine = from_config(load_config())

    assert [voice.id for voice in engine.voices()] == [
        "elevenlabs:abc123",
        "elevenlabs:def456",
    ]
