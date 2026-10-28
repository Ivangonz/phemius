from typing import Any

from fastapi import APIRouter

from phemius.config import load_config
from phemius.services import agent
from phemius.voices import VOICES

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def library_config() -> dict[str, Any]:
    config = load_config()
    return {
        "tones": agent.TONES,
        "voices": VOICES,
        "default_voice": config.default_voice,
        "watch_dir": str(config.watch_dir) if config.watch_dir else None,
        "llm": config.openrouter_api_key is not None,
        "model": config.model,
        "llm_error": agent.last_error,
        "tts": config.voice_engine,
    }
