"""Back up the library to one zip archive.

An archive holds `manifest.json`, `library.db` (a consistent copy with no API
keys and no access token hash) and `audio/<file>` for every audio file.
"""

import os
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

import structlog
from pydantic import BaseModel

from phemius import __version__
from phemius.config import load_config, secret_setting_keys
from phemius.services import maintenance
from phemius.store import backup as backup_store
from phemius.store import database
from phemius.store.backup import SNAPSHOT_AUDIO_DIR, SnapshotAudioFile

FORMAT: Final = "phemius-backup"
FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
DATABASE_NAME = "library.db"
TEMPORARY_PREFIX = ".backup-"

log = structlog.get_logger(__name__)


class BackupManifest(BaseModel):
    format: Literal["phemius-backup"]
    format_version: int
    app_version: str
    created: datetime
    schema_version: int
    documents: int
    versions: int
    audio: int
    audio_files: int


@dataclass(frozen=True)
class BackupArchive:
    path: Path
    filename: str


def create_backup() -> BackupArchive:
    """Write a backup into the library folder. The caller deletes it once sent.

    Written to disk rather than memory, so a large library streams from a file.
    """
    data_dir = load_config().data_dir
    with maintenance.gate.exclusive():
        handle, name = tempfile.mkstemp(
            dir=data_dir, prefix=TEMPORARY_PREFIX, suffix=".zip"
        )
        # mkstemp creates the file owner-only; reopening it keeps that mode.
        os.close(handle)
        path = Path(name)
        try:
            manifest = _write_archive(path, data_dir)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    log.info("library_backed_up", audio_files=manifest.audio_files)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    return BackupArchive(path, f"phemius-backup-{stamp}.zip")


def _write_archive(archive_path: Path, data_dir: Path) -> BackupManifest:
    with tempfile.TemporaryDirectory(dir=data_dir, prefix=TEMPORARY_PREFIX) as work:
        snapshot = Path(work) / DATABASE_NAME
        database.copy_to(snapshot)
        audio_files = backup_store.sanitize_snapshot(snapshot, secret_setting_keys())
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.write(snapshot, DATABASE_NAME, zipfile.ZIP_DEFLATED)
            written = sum(_add_audio_file(archive, item) for item in audio_files)
            manifest = _manifest(snapshot, written)
            archive.writestr(MANIFEST_NAME, manifest.model_dump_json(indent=2))
    return manifest


def _add_audio_file(archive: zipfile.ZipFile, audio_file: SnapshotAudioFile) -> bool:
    # A missing file was already missing from the library; its row still travels.
    if not audio_file.source.is_file():
        return False
    # Audio is already compressed; deflating it again costs time for nothing.
    archive.write(
        audio_file.source, f"{SNAPSHOT_AUDIO_DIR}/{audio_file.name}", zipfile.ZIP_STORED
    )
    return True


def _manifest(snapshot: Path, audio_files: int) -> BackupManifest:
    counts = backup_store.count_library(snapshot)
    return BackupManifest(
        format=FORMAT,
        format_version=FORMAT_VERSION,
        app_version=__version__,
        created=datetime.now(UTC),
        schema_version=counts.schema_version,
        documents=counts.documents,
        versions=counts.versions,
        audio=counts.audio,
        audio_files=audio_files,
    )


def remove_leftovers(data_dir: Path) -> None:
    """Remove temporary backup files a stopped server left behind."""
    for path in data_dir.glob(f"{TEMPORARY_PREFIX}*"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
