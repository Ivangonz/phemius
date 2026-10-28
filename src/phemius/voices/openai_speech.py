"""Narration through OpenAI or any server that implements `/v1/audio/speech`."""

from contextlib import AbstractContextManager
from pathlib import Path

import httpx2
import structlog

from phemius.config import Config
from phemius.errors import VoiceError
from phemius.voices.base import Voice, VoiceCheck
from phemius.voices.http import Provider, error_field, raise_for_status, session
from phemius.voices.text import pack_chunks
from phemius.voices.wav import Clip, read_wav, write_clips

ENGINE_NAME = "openai_speech"
MAX_CHARS = 4096
SYNTHESIS_TIMEOUT_SECONDS = 120.0
CHECK_TIMEOUT_SECONDS = 5.0

KEY_HINT = "Check PHEMIUS_OPENAI_SPEECH_API_KEY."
QUOTA_HINT = "Your speech provider quota is used up; check your plan and billing."
WAV_HINT = 'Use a speech server that supports response_format "wav".'
STATUS_HINTS = {
    400: "Check PHEMIUS_OPENAI_SPEECH_MODEL and PHEMIUS_OPENAI_SPEECH_VOICES.",
    401: KEY_HINT,
    403: KEY_HINT,
    404: "Check PHEMIUS_OPENAI_SPEECH_BASE_URL and PHEMIUS_OPENAI_SPEECH_MODEL.",
    429: "The speech server is rate limiting requests; try again in a minute.",
}

log = structlog.get_logger(__name__)


def _hint_for(response: httpx2.Response) -> str | None:
    # OpenAI answers 429 both for rate limits and for an exhausted quota.
    if error_field(response, "error", "code") == "insufficient_quota":
        return QUOTA_HINT
    return STATUS_HINTS.get(response.status_code)


PROVIDER = Provider(
    engine=ENGINE_NAME,
    name="The speech server",
    unreachable_hint=(
        "Check PHEMIUS_OPENAI_SPEECH_BASE_URL and that the server is running."
    ),
    hint_for=_hint_for,
)


class OpenAISpeechEngine:
    extension = "wav"

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        voice_names: list[str],
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._model = model
        self._voices = [
            Voice(id=f"{ENGINE_NAME}:{name}", label=name.capitalize(), accent=None)
            for name in voice_names
        ]
        self._transport = transport

    def voices(self) -> list[Voice]:
        return self._voices

    def check(self) -> VoiceCheck:
        try:
            with self._session(CHECK_TIMEOUT_SECONDS) as client:
                response = client.get("models")
            # Some self-hosted speech servers do not list models; reaching one is
            # enough to know the URL is right.
            if response.status_code != 404:
                raise_for_status(response, PROVIDER)
        except VoiceError as error:
            return VoiceCheck(False, error.message, error.hint)
        return VoiceCheck(True, "The speech server is reachable.")

    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        voice_name = voice.removeprefix(f"{ENGINE_NAME}:")
        chunks = pack_chunks(script, MAX_CHARS)
        log.info("voice_synthesis_started", engine=ENGINE_NAME, chunks=len(chunks))
        with self._session(SYNTHESIS_TIMEOUT_SECONDS) as client:
            clips = [self._speak(client, chunk, voice_name) for chunk in chunks]
        write_clips(clips, out_path)

    def _speak(self, client: httpx2.Client, text: str, voice_name: str) -> Clip:
        response = client.post(
            "audio/speech",
            json={
                "model": self._model,
                "voice": voice_name,
                "input": text,
                "response_format": "wav",
            },
        )
        raise_for_status(response, PROVIDER)
        return read_wav(response.content, WAV_HINT)

    def _session(self, timeout: float) -> AbstractContextManager[httpx2.Client]:
        return session(
            PROVIDER, self._base_url, self._headers, timeout, self._transport
        )


def from_config(config: Config) -> OpenAISpeechEngine:
    api_key = config.openai_speech_api_key
    return OpenAISpeechEngine(
        base_url=config.openai_speech_base_url,
        api_key=api_key.get_secret_value() if api_key else None,
        model=config.openai_speech_model,
        voice_names=config.openai_speech_voices.split(","),
    )
