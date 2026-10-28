from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from phemius.config import OFFLINE_PROVIDER, load_config
from phemius.models.prompts import TONES
from phemius.services import agent, ffmpeg, script_models, voices

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def library_config() -> dict[str, Any]:
    config = load_config()
    script_model = script_models.active_model()
    return {
        "tones": TONES,
        "voices": {voice.id: voice.label for voice in voices.list_voices()},
        "default_voice": voices.default_voice(),
        "tts_status": asdict(voices.check_engine()),
        "watch_dir": str(config.watch_dir) if config.watch_dir else None,
        "llm": config.script_provider != OFFLINE_PROVIDER,
        "script_provider": script_model.provider,
        "model": script_model.model,
        "llm_error": script_model.error or agent.last_error,
        "llm_hint": script_model.hint,
        "tts": config.voice_engine,
        "ffmpeg": asdict(ffmpeg.check_ffmpeg()),
    }
