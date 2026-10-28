"""Narration with ElevenLabs hosted voices, over its REST API."""

from contextlib import AbstractContextManager
from pathlib import Path

import httpx2
import structlog

from phemius.config import Config
from phemius.errors import VoiceError
from phemius.voices.base import Voice, VoiceCheck
from phemius.voices.http import Provider, error_field, raise_for_status, session
from phemius.voices.text import pack_chunks
from phemius.voices.wav import Clip, write_clips

ENGINE_NAME = "elevenlabs"
BASE_URL = "https://api.elevenlabs.io/v1"
MODEL_ID = "eleven_multilingual_v2"
# The model's per-request limit is 10,000 characters; smaller requests fail
# faster and cost less to retry.
MAX_CHARS = 5000
# Raw 16-bit mono PCM joins without ffmpeg, and 24 kHz is offered on every plan.
SAMPLE_RATE = 24000
SYNTHESIS_TIMEOUT_SECONDS = 120.0
CHECK_TIMEOUT_SECONDS = 5.0

KEY_HINT = "Set ELEVENLABS_API_KEY to a valid ElevenLabs API key."
QUOTA_HINT = "Your ElevenLabs credits are used up; upgrade or wait for the reset."
STATUS_HINTS = {
    401: KEY_HINT,
    403: KEY_HINT,
    404: "Check the voice ids in PHEMIUS_ELEVENLABS_VOICES.",
    429: "ElevenLabs is rate limiting requests; try again in a minute.",
}
# Voices premade for every ElevenLabs account; other ids are labelled by id.
KNOWN_LABELS = {"JBFqnCBsd6RMkjVDRZzb": "George", "EXAVITQu4vr4xnSDxMaL": "Sarah"}

log = structlog.get_logger(__name__)


def _hint_for(response: httpx2.Response) -> str | None:
    # ElevenLabs answers 401 both for a bad key and for exhausted credits.
    if error_field(response, "detail", "status") == "quota_exceeded":
        return QUOTA_HINT
    return STATUS_HINTS.get(response.status_code)


PROVIDER = Provider(
    engine=ENGINE_NAME,
    name="ElevenLabs",
    unreachable_hint="Check your network connection.",
    hint_for=_hint_for,
)


class ElevenLabsEngine:
    extension = "wav"

    def __init__(
        self,
        api_key: str | None,
        voice_ids: list[str],
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._voice_ids = voice_ids
        self._transport = transport

    def voices(self) -> list[Voice]:
        return [
            Voice(
                id=f"{ENGINE_NAME}:{voice_id}",
                label=KNOWN_LABELS.get(voice_id, voice_id),
                accent=None,
            )
            for voice_id in self._voice_ids
        ]

    def check(self) -> VoiceCheck:
        try:
            with self._session(CHECK_TIMEOUT_SECONDS) as client:
                response = client.get(f"voices/{self._voice_ids[0]}")
            raise_for_status(response, PROVIDER)
        except VoiceError as error:
            return VoiceCheck(False, error.message, error.hint)
        return VoiceCheck(True, "ElevenLabs is reachable and the key works.")

    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        voice_id = voice.removeprefix(f"{ENGINE_NAME}:")
        chunks = pack_chunks(script, MAX_CHARS)
        log.info("voice_synthesis_started", engine=ENGINE_NAME, chunks=len(chunks))
        with self._session(SYNTHESIS_TIMEOUT_SECONDS) as client:
            clips = [self._speak(client, chunk, voice_id) for chunk in chunks]
        write_clips(clips, out_path)

    def _speak(self, client: httpx2.Client, text: str, voice_id: str) -> Clip:
        response = client.post(
            f"text-to-speech/{voice_id}",
            params={"output_format": f"pcm_{SAMPLE_RATE}"},
            json={"text": text, "model_id": MODEL_ID},
        )
        raise_for_status(response, PROVIDER)
        return Clip(
            channels=1, sample_width=2, sample_rate=SAMPLE_RATE, frames=response.content
        )

    def _session(self, timeout: float) -> AbstractContextManager[httpx2.Client]:
        if not self._api_key:
            raise VoiceError("ElevenLabs needs an API key.", hint=KEY_HINT)
        return session(
            PROVIDER,
            BASE_URL,
            {"xi-api-key": self._api_key},
            timeout,
            self._transport,
        )


def from_config(config: Config) -> ElevenLabsEngine:
    api_key = config.elevenlabs_api_key
    return ElevenLabsEngine(
        api_key=api_key.get_secret_value() if api_key else None,
        voice_ids=config.elevenlabs_voices.split(","),
    )
