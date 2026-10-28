from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from phemius.services import backup, library

router = APIRouter(prefix="/api/library", tags=["library"])


class AudioDeleted(BaseModel):
    deleted_files: int


@router.post(
    "/backup",
    response_class=FileResponse,
    responses={200: {"content": {"application/zip": {}}}},
)
def back_up_library() -> FileResponse:
    """Download a zip of the library: database, audio files and settings
    without API keys or the access token."""
    archive = backup.create_backup()
    return FileResponse(
        archive.path,
        media_type="application/zip",
        filename=archive.filename,
        headers={"Cache-Control": "no-store"},
        background=BackgroundTask(archive.path.unlink, missing_ok=True),
    )


@router.delete("/audio")
def delete_all_audio() -> AudioDeleted:
    """Delete every audio file. Documents and scripts stay, and each audio's job
    becomes cancelled so a retry narrates its saved script again."""
    return AudioDeleted(deleted_files=library.delete_all_audio())
