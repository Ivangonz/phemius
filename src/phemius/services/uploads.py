"""Import uploaded files into the library."""

import shutil
import tempfile
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel

from phemius.services import ingest, pipeline


class UploadResult(BaseModel):
    file: str
    doc_id: int | None = None
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
            document_id, is_created = pipeline.import_file(path, source=filename)
        except Exception as error:  # reported per file in the response
            return UploadResult(file=filename, error=str(error))
    if is_created and is_auto_audio:
        pipeline.build_audio(document_id)
    return UploadResult(file=filename, doc_id=document_id, duplicate=not is_created)
