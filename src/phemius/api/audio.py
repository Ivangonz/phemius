from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from phemius.errors import NotFoundError
from phemius.store import audio as audio_store
from phemius.store.audio import Audio

router = APIRouter(prefix="/api/audio", tags=["audio"])

MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".mp3": "audio/mpeg",
}


@router.get("/{audio_id}")
def get_audio(audio_id: int) -> Audio:
    audio = audio_store.get_audio(audio_id)
    if audio is None:
        raise NotFoundError(f"Audio {audio_id} not found")
    return audio


@router.get("/{audio_id}/file", response_class=FileResponse)
def get_audio_file(audio_id: int) -> FileResponse:
    audio = audio_store.get_audio(audio_id)
    if audio is None or audio["status"] != "done" or not audio["path"]:
        raise NotFoundError(
            f"Audio {audio_id} is not ready", hint="Wait for generation to finish."
        )
    path = Path(audio["path"])
    media_type = MEDIA_TYPES.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media_type)
