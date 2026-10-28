from typing import Annotated

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from phemius.api.pagination import DEFAULT_PAGE_SIZE, Limit, Offset, Page
from phemius.errors import InvalidInputError, NotFoundError
from phemius.models.prompts import TONES
from phemius.services import pipeline
from phemius.services.uploads import UploadResult, import_upload
from phemius.store import documents as document_store
from phemius.store.documents import Document, DocumentSummary, VersionSummary

router = APIRouter(prefix="/api/docs", tags=["docs"])


class AudioRequest(BaseModel):
    tone: str | None = None
    voice: str | None = None


class AudioCreated(BaseModel):
    audio_id: int


@router.get("")
def list_documents() -> list[DocumentSummary]:
    return document_store.list_documents()


@router.post("")
def upload_documents(
    files: Annotated[list[UploadFile], File()], auto_audio: bool = True
) -> list[UploadResult]:
    return [
        import_upload(upload.filename or "upload", upload.file, auto_audio)
        for upload in files
    ]


@router.get("/{document_id}")
def get_document(document_id: int) -> Document:
    document = document_store.get_document(document_id)
    if document is None:
        raise NotFoundError(f"Document {document_id} not found")
    return document


@router.get("/{document_id}/versions")
def list_versions(
    document_id: int, limit: Limit = DEFAULT_PAGE_SIZE, offset: Offset = 0
) -> Page[VersionSummary]:
    page = document_store.list_versions(document_id, limit, offset)
    if page is None:
        raise NotFoundError(f"Document {document_id} not found")
    return Page(items=page.items, total=page.total, limit=limit, offset=offset)


@router.post("/{document_id}/audio")
def create_audio(document_id: int, request: AudioRequest) -> AudioCreated:
    if request.tone and request.tone not in TONES:
        raise InvalidInputError(
            f"Unknown tone; choose from {list(TONES)}", field="tone"
        )
    audio_id = pipeline.build_audio(document_id, request.tone, request.voice)
    return AudioCreated(audio_id=audio_id)
