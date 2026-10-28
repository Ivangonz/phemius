"""Local narration with Kokoro (optional `kokoro` extra, Python 3.12)."""

from importlib.util import find_spec
from pathlib import Path
from typing import Any

from phemius.errors import VoiceError
from phemius.voices.base import Voice, VoiceCheck
from phemius.voices.text import split_chunks

ENGINE_NAME = "kokoro"
SAMPLE_RATE = 24000
PAUSE_SECONDS = 0.25
REQUIRED_MODULES = ("kokoro", "soundfile", "numpy")
INSTALL_HINT = "Run `uv sync --extra kokoro`, or set PHEMIUS_TTS=stub to test."

# Kokoro voice names start with the accent (a = American, b = British) and the
# gender; the accent letter is also the KPipeline language code.
ACCENTS = {"a": "American English", "b": "British English"}
VOICE_LABELS = {
    "af_heart": "Heart, female (default)",
    "af_bella": "Bella, female",
    "af_nicole": "Nicole, female, soft",
    "af_sarah": "Sarah, female",
    "af_sky": "Sky, female",
    "am_adam": "Adam, male",
    "am_michael": "Michael, male",
    "bf_emma": "Emma, female",
    "bf_isabella": "Isabella, female",
    "bm_george": "George, male",
    "bm_lewis": "Lewis, male",
}
VOICES = [
    Voice(id=f"{ENGINE_NAME}:{name}", label=label, accent=ACCENTS[name[0]])
    for name, label in VOICE_LABELS.items()
]


def _is_installed() -> bool:
    return all(find_spec(module) is not None for module in REQUIRED_MODULES)


class KokoroEngine:
    extension = "wav"

    def __init__(self) -> None:
        self._pipelines: dict[str, Any] = {}  # one KPipeline per accent

    def voices(self) -> list[Voice]:
        return VOICES

    def check(self) -> VoiceCheck:
        if not _is_installed():
            return VoiceCheck(False, "Kokoro is not installed.", INSTALL_HINT)
        return VoiceCheck(True, "Kokoro is installed.")

    def _pipeline_for(self, accent: str) -> Any:
        if accent not in self._pipelines:
            from kokoro import KPipeline

            self._pipelines[accent] = KPipeline(lang_code=accent)
        return self._pipelines[accent]

    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        if not _is_installed():
            raise VoiceError("Kokoro is not installed.", INSTALL_HINT)
        import numpy as np
        import soundfile

        name = voice.removeprefix(f"{ENGINE_NAME}:")
        pipeline = self._pipeline_for(name[0])
        pause = np.zeros(int(SAMPLE_RATE * PAUSE_SECONDS), dtype="float32")
        parts = []
        for chunk in split_chunks(script):
            for _, _, audio in pipeline(chunk, voice=name, speed=1.0):
                parts.extend([audio, pause])
        if not parts:
            raise VoiceError("Kokoro produced no audio for this script.")
        soundfile.write(str(out_path), np.concatenate(parts), SAMPLE_RATE)
