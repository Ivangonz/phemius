from dataclasses import asdict
from urllib.parse import quote

from fastapi import APIRouter, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from phemius.api.audio import MEDIA_TYPES, signed_file_url
from phemius.api.pagination import DEFAULT_PAGE_SIZE, Limit, Offset, Page
from phemius.api.params import VoiceId
from phemius.services import access as access_service
from phemius.services import previews, voice_downloads, voices
from phemius.services.library_config import VoiceEngineStatus
from phemius.services.voice_downloads import DownloadProgress
from phemius.services.voices import VoiceOrder, VoiceView

router = APIRouter(prefix="/api/voices", tags=["voices"])


class VoicePreview(BaseModel):
    url: str
    expires: int


@router.get("")
def list_voices(
    order_by: VoiceOrder = "default",
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> Page[VoiceView]:
    """The configured engine's voices, default first. Sends no provider request."""
    items, total = voices.list_voice_views(order_by, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


# Plain `def`: a hosted engine's check waits on a paid provider request.
@router.post("/check")
def check_voice_engine() -> VoiceEngineStatus:
    """Test the configured voice engine now. Hosted engines send a real request.

    Always a fresh check: once hosted checks are cached (#64), this bypasses it.
    """
    return VoiceEngineStatus(**asdict(voices.check_engine()))


@router.post("/{voice_id}/download", status_code=status.HTTP_202_ACCEPTED)
def download_voice(voice_id: VoiceId) -> DownloadProgress:
    """Download a voice in the background; its progress shows in the voice list.

    Asking again while it downloads returns the same download. Fetches from the
    voice catalogue host, never a paid provider.
    """
    return voice_downloads.download_voice(voice_id)


# Plain `def`: synthesis waits for the voice engine and for narration's turn.
@router.post("/{voice_id}/preview")
def preview_voice(voice_id: VoiceId) -> VoicePreview:
    """A short-lived URL to a sample of the voice, synthesized on the first call.

    Later calls reuse the cached sample, so a hosted engine is paid once.
    """
    catalog_id = previews.create_preview(voice_id)
    signed = access_service.sign_preview_url(catalog_id)
    path = f"/api/voices/{quote(catalog_id, safe=':')}/preview/file"
    return VoicePreview(url=signed_file_url(path, signed), expires=signed.expires)


@router.get("/{voice_id}/preview/file", response_class=FileResponse)
def get_preview_file(voice_id: VoiceId) -> FileResponse:
    path = previews.cached_preview(voice_id)
    media_type = MEDIA_TYPES.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media_type)
