"""Lightweight local narration with Piper (optional `piper` extra).

Voices download on demand from a pinned revision of the rhasspy/piper-voices
catalogue into `<data folder>/voices/piper`.
"""

import wave
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path
from typing import Any

import structlog

from phemius.config import load_config
from phemius.errors import VoiceError
from phemius.voices.base import Voice, VoiceCheck
from phemius.voices.downloads import Fetch, Progress, download_verified, fetch_url

log = structlog.get_logger(__name__)

ENGINE_NAME = "piper"
INSTALL_HINT = "Run `uv sync --extra piper`, or set PHEMIUS_TTS=stub to test."
# Pinning the revision keeps the checksums below valid if a voice is re-uploaded.
CATALOGUE_REVISION = "5041a7a49ae5b3a0f30e6837769eb03fdbb231bd"
CATALOGUE_URL = (
    f"https://huggingface.co/rhasspy/piper-voices/resolve/{CATALOGUE_REVISION}"
)
MODEL_SUFFIX = ".onnx"
CONFIG_SUFFIX = ".onnx.json"


@dataclass(frozen=True)
class VoiceFile:
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class CatalogueVoice:
    """A downloadable voice. `name` is `<language>-<speaker>-<quality>`."""

    name: str
    label: str
    accent: str
    license: str
    model: VoiceFile
    config: VoiceFile

    @property
    def size_bytes(self) -> int:
        return self.model.size_bytes + self.config.size_bytes

    def url(self, suffix: str) -> str:
        language, speaker, quality = self.name.split("-")
        family = language.split("_")[0]
        folder = f"{family}/{language}/{speaker}/{quality}"
        return f"{CATALOGUE_URL}/{folder}/{self.name}{suffix}"


# Licenses come from each voice's MODEL_CARD; keep the README table in sync.
CATALOGUE = [
    CatalogueVoice(
        name="en_US-lessac-medium",
        label="Lessac, female (default)",
        accent="American English",
        license="Blizzard 2013 Lessac license (non-commercial)",
        model=VoiceFile(
            "5efe09e69902187827af646e1a6e9d269dee769f9877d17b16b1b46eeaaf019f",
            63201294,
        ),
        config=VoiceFile(
            "efe19c417bed055f2d69908248c6ba650fa135bc868b0e6abb3da181dab690a0",
            4885,
        ),
    ),
    CatalogueVoice(
        name="en_US-joe-medium",
        label="Joe, male",
        accent="American English",
        license="CC0",
        model=VoiceFile(
            "58afce0321b8d9c46d7cdf9c16500cc55a793b4220212dba6b70fb788b3baf06",
            63201294,
        ),
        config=VoiceFile(
            "3d6d5410b3795cb1950595247ef8f06190719e6fdbfa3a2356d8ec368e1aad33",
            4794,
        ),
    ),
    CatalogueVoice(
        name="en_GB-cori-medium",
        label="Cori, female",
        accent="British English",
        license="Public domain (LibriVox)",
        model=VoiceFile(
            "1899f98e5fb8310154f3c2973f4b8a929ba7245e722b3d3a85680b833d95f10d",
            63531379,
        ),
        config=VoiceFile(
            "e262c16d7f192f69d4edd6b4ef8a5915379e67495fcc402f1ab15eeb33da3d36",
            4966,
        ),
    ),
    CatalogueVoice(
        name="en_GB-northern_english_male-medium",
        label="Northern English, male",
        accent="British English",
        license="CC BY-SA 4.0",
        model=VoiceFile(
            "57a219ae8e638873db7d18893304be5069c42868f392bb95c3ff17f0690d0689",
            63201294,
        ),
        config=VoiceFile(
            "69557ed3d974463453e9b0c09dd99a7ed0e52b8b87b64b357dbeeb2540a97d47",
            4847,
        ),
    ),
]


def _is_installed() -> bool:
    return find_spec("piper") is not None


def _ignore_progress(done: int, total: int) -> None:
    pass


def _catalogue_voice(voice: str) -> CatalogueVoice:
    name = voice.removeprefix(f"{ENGINE_NAME}:")
    for entry in CATALOGUE:
        if entry.name == name:
            return entry
    names = ", ".join(f"{ENGINE_NAME}:{entry.name}" for entry in CATALOGUE)
    raise VoiceError(f"Unknown Piper voice '{voice}'.", hint=f"Choose one of: {names}.")


class PiperEngine:
    extension = "wav"

    def __init__(
        self, voices_dir: Path | None = None, fetch: Fetch = fetch_url
    ) -> None:
        self._voices_dir = voices_dir
        self._fetch = fetch
        self._loaded: dict[str, Any] = {}  # one PiperVoice per voice name

    def voices(self) -> list[Voice]:
        return [
            Voice(
                id=f"{ENGINE_NAME}:{entry.name}",
                label=entry.label,
                accent=entry.accent,
                is_installed=self._is_downloaded(entry),
                size_bytes=entry.size_bytes,
            )
            for entry in CATALOGUE
        ]

    def check(self) -> VoiceCheck:
        if not _is_installed():
            return VoiceCheck(False, "Piper is not installed.", INSTALL_HINT)
        if not any(self._is_downloaded(entry) for entry in CATALOGUE):
            # Still ready: the first narration downloads its voice.
            return VoiceCheck(
                True,
                "Piper voice not downloaded yet.",
                "The first narration downloads its voice (about 63 MB).",
            )
        return VoiceCheck(True, "Piper is ready.")

    def download(self, voice: str, on_progress: Progress = _ignore_progress) -> Path:
        """Download `voice` unless it is already installed; return its model path.

        Raises `VoiceError` on a network failure or a checksum mismatch.
        """
        entry = _catalogue_voice(voice)
        missing = [
            (suffix, file)
            for suffix, file in self._files(entry)
            if not self._path(entry, suffix).exists()
        ]
        if missing:
            self._download_files(entry, missing, on_progress)
        return self._path(entry, MODEL_SUFFIX)

    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        if not _is_installed():
            raise VoiceError("Piper is not installed.", INSTALL_HINT)
        piper_voice = self._load(voice)
        try:
            with wave.open(str(out_path), "wb") as wav_file:
                piper_voice.synthesize_wav(script, wav_file)
        except wave.Error as error:  # raised on close when nothing was written
            raise VoiceError("Piper produced no audio for this script.") from error

    def _load(self, voice: str) -> Any:
        if voice not in self._loaded:
            from piper import PiperVoice

            model_path = self.download(voice)
            self._loaded[voice] = PiperVoice.load(str(model_path))
        return self._loaded[voice]

    def _download_files(
        self,
        entry: CatalogueVoice,
        files: list[tuple[str, VoiceFile]],
        on_progress: Progress,
    ) -> None:
        total = sum(file.size_bytes for _, file in files)
        done = 0

        def on_chunk(size: int) -> None:
            nonlocal done
            done += size
            on_progress(done, total)

        self._directory().mkdir(parents=True, exist_ok=True)
        log.info("piper_voice_download_started", voice=entry.name, bytes=total)
        for suffix, file in files:
            download_verified(
                entry.url(suffix),
                self._path(entry, suffix),
                sha256=file.sha256,
                size_bytes=file.size_bytes,
                fetch=self._fetch,
                on_chunk=on_chunk,
            )
        log.info("piper_voice_download_finished", voice=entry.name)

    def _files(self, entry: CatalogueVoice) -> list[tuple[str, VoiceFile]]:
        return [(CONFIG_SUFFIX, entry.config), (MODEL_SUFFIX, entry.model)]

    def _is_downloaded(self, entry: CatalogueVoice) -> bool:
        return all(
            self._path(entry, suffix).exists() for suffix, _ in self._files(entry)
        )

    def _path(self, entry: CatalogueVoice, suffix: str) -> Path:
        return self._directory() / f"{entry.name}{suffix}"

    def _directory(self) -> Path:
        # Resolved per call: the engine is cached but the data folder can change.
        return self._voices_dir or load_config().data_dir / "voices" / ENGINE_NAME
