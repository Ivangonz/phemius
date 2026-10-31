from dataclasses import asdict

from fastapi import APIRouter, status

from phemius.api.pagination import DEFAULT_PAGE_SIZE, Limit, Offset, Page
from phemius.api.params import VoiceId
from phemius.services import voice_downloads, voices
from phemius.services.library_config import VoiceEngineStatus
from phemius.services.voice_downloads import DownloadProgress
from phemius.services.voices import VoiceOrder, VoiceView

router = APIRouter(prefix="/api/voices", tags=["voices"])


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
