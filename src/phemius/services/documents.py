"""Documents in the library beyond importing them (see `services/pipeline.py`)."""

from pathlib import Path

import structlog

from phemius.config import load_config
from phemius.errors import DocumentBusyError, LibraryBusyError, NotFoundError
from phemius.services import maintenance, narration_parts
from phemius.store import documents as document_store

log = structlog.get_logger(__name__)


def delete_document(document_id: int) -> None:
    """Delete a document with its versions, audio and waiting jobs, then its
    audio files. A file already missing is not an error.

    Raises `NotFoundError`, `DocumentBusyError` while one of its jobs runs, and
    `LibraryBusyError` while a backup or restore holds the library.
    """
    # A turn keeps a backup or restore from starting until the files are gone.
    with maintenance.gate.worker_turn() as is_allowed:
        if not is_allowed:
            raise LibraryBusyError(
                "A backup or restore is in progress.",
                hint="Wait for it to finish, then delete the document again.",
            )
        deleted = document_store.delete_document(document_id)
        for recorded in deleted.audio_paths:
            Path(recorded).unlink(missing_ok=True)
        if deleted.outcome == "deleted":
            narration_parts.remove_leftovers(load_config().audio_dir)
    if deleted.outcome == "missing":
        raise NotFoundError(f"Document {document_id} not found")
    if deleted.outcome == "job_running":
        raise DocumentBusyError(
            "A job for this document is running.", hint=maintenance.JOB_RUNNING_HINT
        )
    log.info(
        "document_deleted", document_id=document_id, files=len(deleted.audio_paths)
    )
