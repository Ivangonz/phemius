from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from phemius.api.params import Id
from phemius.errors import NotFoundError
from phemius.services import access as access_service
from phemius.services.access import AudioUrlSignature
from phemius.store import audio as audio_store
from phemius.store.audio import Audio

router = APIRouter(prefix="/api/audio", tags=["audio"])

MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".mp3": "audio/mpeg",
}


class AudioUrl(BaseModel):
    url: str
    expires: int


@router.get("/{audio_id}")
def get_audio(audio_id: Id) -> Audio:
    audio = audio_store.get_audio(audio_id)
    if audio is None:
        raise NotFoundError(f"Audio {audio_id} not found")
    return audio


@router.get("/{audio_id}/url")
def get_audio_url(audio_id: Id) -> AudioUrl:
    """A short-lived URL for the audio file that works without the token header."""
    _ready_audio_path(audio_id)
    signed = access_service.sign_audio_url(audio_id)
    url = signed_file_url(f"/api/audio/{audio_id}/file", signed)
    return AudioUrl(url=url, expires=signed.expires)


def signed_file_url(path: str, signed: AudioUrlSignature) -> str:
    """`path` with its signature; unsigned in local mode, where no token exists."""
    if signed.signature is None:
        return path
    return f"{path}?expires={signed.expires}&sig={signed.signature}"


@router.get("/{audio_id}/file", response_class=FileResponse)
def get_audio_file(audio_id: Id) -> FileResponse:
    path = _ready_audio_path(audio_id)
    media_type = MEDIA_TYPES.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media_type)


def _ready_audio_path(audio_id: int) -> Path:
    audio = audio_store.get_audio(audio_id)
    if audio is None or audio["status"] != "done" or not audio["path"]:
        raise NotFoundError(
            f"Audio {audio_id} is not ready", hint="Wait for generation to finish."
        )
    return Path(audio["path"])
