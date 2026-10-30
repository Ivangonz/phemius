"""Short voice samples, synthesized once per voice and engine setup, then cached.

Hosted engines charge per request, so a sample is only made when the user asks
for it and is kept under `previews/{engine}/` in the data folder.
"""

import hashlib
import json
import os
import tempfile
from pathlib import Path

import structlog

from phemius.config import Config, load_config, secret_setting_keys
from phemius.errors import NotFoundError
from phemius.services import synthesis
from phemius.store.permissions import create_private_dir
from phemius.voices import Voice, VoiceEngine, get_engine, namespace_voice

PREVIEWS_DIR = "previews"

log = structlog.get_logger(__name__)


def create_preview(requested: str) -> str:
    """The catalog id of `requested`, with its sample cached. Calls the engine once."""
    config = load_config()
    engine = get_engine(config)
    voice = _catalog_voice(config, engine, requested)
    path = _cache_path(config, engine, voice.id)
    if not path.is_file():
        _synthesize_once(engine, voice, path)
    return voice.id


def cached_preview(requested: str) -> Path:
    """The cached sample of `requested`. Never synthesizes."""
    config = load_config()
    engine = get_engine(config)
    voice = _catalog_voice(config, engine, requested)
    path = _cache_path(config, engine, voice.id)
    if not path.is_file():
        raise NotFoundError("No preview yet", hint="Choose Preview to make one.")
    return path


def _catalog_voice(config: Config, engine: VoiceEngine, requested: str) -> Voice:
    voice_id = namespace_voice(config.voice_engine, requested)
    for voice in engine.voices():
        if voice.id == voice_id:
            return voice
    raise NotFoundError(
        f"Unknown {config.voice_engine} voice", hint="Choose a voice from the list."
    )


def _cache_path(config: Config, engine: VoiceEngine, voice_id: str) -> Path:
    # A digest rather than the id: configured voice names may hold any character.
    folder = config.data_dir / PREVIEWS_DIR / config.voice_engine
    return folder / f"{_cache_key(config, voice_id)}.{engine.extension}"


def _cache_key(config: Config, voice_id: str) -> str:
    # The engine's own non-secret settings (base URL, model) are in the key, so a
    # sample from another server or model is never served.
    secrets = set(secret_setting_keys())
    engine_settings = {
        key: value
        for key, value in config.model_dump(mode="json").items()
        if key.startswith(f"{config.voice_engine}_") and key not in secrets
    }
    material = json.dumps([voice_id, engine_settings], sort_keys=True)
    return hashlib.sha256(material.encode()).hexdigest()[:32]


def _synthesize_once(engine: VoiceEngine, voice: Voice, path: Path) -> None:
    create_private_dir(path.parent.parent)
    create_private_dir(path.parent)
    with synthesis.lock:
        # Another request may have made it while this one waited for the lock.
        if path.is_file():
            return
        log.info("voice_preview_started", voice=voice.id)
        _write_atomically(engine, voice, path)
    log.info("voice_preview_cached", voice=voice.id)


def _write_atomically(engine: VoiceEngine, voice: Voice, path: Path) -> None:
    handle, temporary = tempfile.mkstemp(dir=path.parent, suffix=".pending")
    os.close(handle)
    pending = Path(temporary)
    try:
        engine.synthesize(voice.sample_text, pending, voice.id)
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)
