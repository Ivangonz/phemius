from dataclasses import asdict
from typing import Any

from fastapi import APIRouter

from phemius.config import load_config
from phemius.services import agent, voices

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def library_config() -> dict[str, Any]:
    config = load_config()
    return {
        "tones": agent.TONES,
        "voices": {voice.id: voice.label for voice in voices.list_voices()},
        "default_voice": voices.default_voice(),
        "tts_status": asdict(voices.check_engine()),
        "watch_dir": str(config.watch_dir) if config.watch_dir else None,
        "llm": config.openrouter_api_key is not None,
        "model": config.model,
        "llm_error": agent.last_error,
        "tts": config.voice_engine,
    }
