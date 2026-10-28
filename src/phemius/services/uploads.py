"""Import uploaded files into the library."""

import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel

from phemius.errors import PhemiusError
from phemius.services import ingest, pipeline


class UploadResult(BaseModel):
    file: str
    doc_id: int | None = None
    version: int | None = None
    duplicate: bool | None = None
    error: str | None = None


def import_upload(
    filename: str, content: BinaryIO, is_auto_audio: bool
) -> UploadResult:
    name = Path(filename).name or "upload"
    suffix = Path(name).suffix.lower()
    if suffix not in ingest.SUPPORTED:
        return UploadResult(file=filename, error=f"unsupported type {suffix}")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / name
        with path.open("wb") as handle:
            shutil.copyfileobj(content, handle)
        try:
            stored = pipeline.import_file(path, source=filename)
        except Exception as error:  # reported per file in the response
            return UploadResult(file=filename, error=str(error))
    is_duplicate = stored.outcome == "unchanged"
    result = UploadResult(
        file=filename,
        doc_id=stored.document_id,
        version=stored.version,
        duplicate=is_duplicate,
    )
    if is_auto_audio and not is_duplicate:
        try:
            pipeline.build_audio(stored.document_id)
        except PhemiusError as error:  # the document is kept; only audio failed
            result.error = pipeline.error_text(error)
    return result
