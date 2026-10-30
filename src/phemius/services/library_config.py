"""The library's configuration as the UI reads it; never holds secrets."""

from dataclasses import asdict

from pydantic import BaseModel

from phemius.config import OFFLINE_PROVIDER, load_config
from phemius.models.prompts import TONES
from phemius.services import agent, ffmpeg, script_models, voices
from phemius.services.ffmpeg import FfmpegCheckStatus


class VoiceEngineStatus(BaseModel):
    """Whether the configured voice engine can synthesize, and how to fix it."""

    is_ready: bool
    message: str
    hint: str | None = None


class FfmpegStatus(BaseModel):
    """Whether ffmpeg can convert audio; missing is optional, WAV is kept."""

    is_present: bool
    version: str | None
    status: FfmpegCheckStatus
    message: str
    hint: str | None = None


class LibraryConfig(BaseModel):
    tones: dict[str, str]
    voices: dict[str, str]
    default_voice: str | None
    tts_status: VoiceEngineStatus
    llm: bool
    script_provider: str
    model: str
    llm_error: str | None
    llm_hint: str | None
    tts: str
    ffmpeg: FfmpegStatus


def describe_library() -> LibraryConfig:
    """The tones, voices, engines and script model the library is set up with."""
    config = load_config()
    script_model = script_models.active_model()
    return LibraryConfig(
        tones=TONES,
        voices={voice.id: voice.label for voice in voices.list_voices()},
        default_voice=voices.default_voice(),
        tts_status=VoiceEngineStatus(**asdict(voices.check_engine())),
        llm=config.script_provider != OFFLINE_PROVIDER,
        script_provider=script_model.provider,
        model=script_model.model,
        llm_error=script_model.error or agent.last_error,
        llm_hint=script_model.hint,
        tts=config.voice_engine,
        ffmpeg=FfmpegStatus(**asdict(ffmpeg.check_ffmpeg())),
    )
