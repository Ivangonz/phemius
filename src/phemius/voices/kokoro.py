"""Local narration with Kokoro (optional `kokoro` extra, Python 3.12)."""

from pathlib import Path
from typing import Any

from phemius.errors import VoiceError
from phemius.voices.text import split_chunks

SAMPLE_RATE = 24000
PAUSE_SECONDS = 0.25

# The first letter is the accent (a = American, b = British), the second is gender.
VOICES = {
    "af_heart": "American, female (default)",
    "af_bella": "American, female",
    "af_nicole": "American, female, soft",
    "af_sarah": "American, female",
    "af_sky": "American, female",
    "am_adam": "American, male",
    "am_michael": "American, male",
    "bf_emma": "British, female",
    "bf_isabella": "British, female",
    "bm_george": "British, male",
    "bm_lewis": "British, male",
}

INSTALL_HINT = "Run `uv sync --extra kokoro`, or set PHEMIUS_TTS=stub to test."


class KokoroEngine:
    extension = "wav"

    def __init__(self) -> None:
        self._pipelines: dict[str, Any] = {}  # one KPipeline per accent

    def _pipeline_for(self, voice: str) -> Any:
        accent = voice[0]
        if accent not in self._pipelines:
            try:
                from kokoro import KPipeline
            except ImportError as error:
                raise VoiceError("Kokoro is not installed.", INSTALL_HINT) from error
            self._pipelines[accent] = KPipeline(lang_code=accent)
        return self._pipelines[accent]

    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        pipeline = self._pipeline_for(voice)
        import numpy as np
        import soundfile

        pause = np.zeros(int(SAMPLE_RATE * PAUSE_SECONDS), dtype="float32")
        parts = []
        for chunk in split_chunks(script):
            for _, _, audio in pipeline(chunk, voice=voice, speed=1.0):
                parts.extend([audio, pause])
        if not parts:
            raise VoiceError("Kokoro produced no audio for this script.")
        soundfile.write(str(out_path), np.concatenate(parts), SAMPLE_RATE)
