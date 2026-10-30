"""Narrated sections kept on disk until joined, so a retry resumes narration.

Each part is `audio/parts/{audio_id}/{index}-{digest}.wav`. The digest is of the
section's script and voice, so a part from an older script or another voice is
never found and that section is narrated again.
"""

import hashlib
import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path

import structlog

from phemius.services import synthesis
from phemius.store import audio as audio_store
from phemius.store.permissions import create_private_dir
from phemius.voices.base import VoiceEngine
from phemius.voices.wav import WavFormat, complete_wav_format

log = structlog.get_logger(__name__)

PARTS_DIR = "parts"
# Before parts were kept, they were `{audio_id}.part{n}.wav` in the audio folder.
LEGACY_PART_PATTERN = "*.part*.wav"
# Bounded so a stray folder name cannot overflow an SQLite integer.
_AUDIO_ID = re.compile(r"[0-9]{1,18}")


def parts_dir(audio_dir: Path, audio_id: int) -> Path:
    return audio_dir / PARTS_DIR / str(audio_id)


def narrated_parts(
    engine: VoiceEngine,
    folder: Path,
    scripts: list[str],
    voice: str,
    should_continue: Callable[[], bool],
) -> list[Path] | None:
    """Each section's part in order, narrating only those not already on disk.

    None if stopped before the last section; the parts so far are kept. A part
    on disk is reused only if it is complete WAV in the first part's format.
    """
    create_private_dir(folder.parent)
    create_private_dir(folder)
    parts: list[Path] = []
    expected: WavFormat | None = None
    for index, script in enumerate(scripts):
        if not should_continue():
            return None
        part = _part_path(folder, index, script, voice)
        if _is_reusable(part, expected):
            log.info("section_part_reused", audio_id=folder.name, index=index)
        else:
            _narrate_part(engine, script, voice, part, index)
        expected = expected or complete_wav_format(part)
        parts.append(part)
    return parts


def _part_path(folder: Path, index: int, script: str, voice: str) -> Path:
    digest = hashlib.sha256(json.dumps([voice, script]).encode()).hexdigest()
    return folder / f"{index}-{digest}.wav"


def _is_reusable(part: Path, expected: WavFormat | None) -> bool:
    found = complete_wav_format(part)
    return found is not None and expected in (None, found)


def _narrate_part(
    engine: VoiceEngine, script: str, voice: str, part: Path, index: int
) -> None:
    for stale in part.parent.glob(f"{index}-*.wav"):
        stale.unlink(missing_ok=True)
    # Renamed once written, so a part cut off mid-write never has a part's name.
    pending = part.with_name(f"{index}.pending.wav")
    with synthesis.lock:
        engine.synthesize(script, pending, voice)
    pending.replace(part)


def remove_parts(audio_dir: Path, audio_id: int) -> None:
    _remove(parts_dir(audio_dir, audio_id))


def remove_all(audio_dir: Path) -> None:
    _remove(audio_dir / PARTS_DIR)


def remove_leftovers(audio_dir: Path) -> None:
    """Remove the parts of audio no longer in the library, and legacy parts."""
    for legacy in audio_dir.glob(LEGACY_PART_PATTERN):
        if legacy.is_file():
            legacy.unlink(missing_ok=True)
    root = audio_dir / PARTS_DIR
    if not root.is_dir():
        return
    folders = list(root.iterdir())
    audio_ids = [int(path.name) for path in folders if _AUDIO_ID.fullmatch(path.name)]
    kept = {str(audio_id) for audio_id in audio_store.existing_audio_ids(audio_ids)}
    for folder in folders:
        if folder.name not in kept:
            _remove(folder)


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)
