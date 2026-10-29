"""Restore the library from a backup archive (see `services/backup.py`).

The archive is checked and unpacked into a private folder inside the library
folder, migrated there, and only then swapped in: the audio folder by two
renames, the database by SQLite's backup API in one transaction. Until the
swap succeeds the previous library stays in place.

API keys and the access token belong to this installation, not to a library:
they are never read from an archive, and the current ones are kept.
"""

import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

import structlog
from pydantic import BaseModel, ValidationError

from phemius.config import Config, load_config, secret_setting_keys
from phemius.errors import InvalidBackupError
from phemius.services import maintenance, sources
from phemius.services.backup import (
    DATABASE_NAME,
    FORMAT,
    FORMAT_VERSION,
    MANIFEST_NAME,
    RESTORE_PREFIX,
    BackupManifest,
)
from phemius.store import access as access_store
from phemius.store import backup as backup_store
from phemius.store import database
from phemius.store import settings as settings_store
from phemius.store.backup import SNAPSHOT_AUDIO_DIR, InstallationState
from phemius.store.migrations import MIGRATIONS
from phemius.store.permissions import create_private_dir, create_private_file

MAX_MEMBERS = 100_000
MAX_MANIFEST_BYTES = 64 * 1024
MAX_UNPACKED_BYTES = 50 * 1024**3
DISK_HEADROOM_BYTES = 100 * 1024**2
# One flat name per file, never hidden: nothing an archive names can leave
# the folder it is unpacked into.
AUDIO_MEMBER = re.compile(
    rf"{SNAPSHOT_AUDIO_DIR}/([A-Za-z0-9_-][A-Za-z0-9._-]{{0,254}})"
)
# Kept from this installation, like the secrets. The endpoints and the
# provider and engine choose where this installation's keys are sent, so an
# archive must not redirect them; the access mode must not open this server to
# the network on the next start; a watched folder is a path on this machine,
# and so are folder sources, which `InstallationState.sources` keeps.
INSTALLATION_SETTINGS = [
    "access_mode",
    "script_provider",
    "script_base_url",
    "ollama_url",
    "voice_engine",
    "openai_speech_base_url",
    "watch_dir",
]

DAMAGED_HINT = "Download a new backup from Settings and try again."

log = structlog.get_logger(__name__)


class BackupSummary(BaseModel):
    app_version: str
    created: datetime
    schema_version: int
    documents: int
    versions: int
    audio: int
    audio_files: int
    queued_jobs: int


class RestoreResult(BackupSummary):
    # Always true: a restore pauses the queue so restored jobs wait for Resume.
    is_queue_paused: bool


@dataclass(frozen=True)
class StagedLibrary:
    db_path: Path
    audio_dir: Path
    summary: BackupSummary


def inspect_backup(archive: BinaryIO) -> BackupSummary:
    """Check an archive and report what it holds, without changing the library."""
    with _staged(archive, load_config().data_dir) as (staged, _work):
        return staged.summary


def restore_backup(archive: BinaryIO) -> RestoreResult:
    """Replace the library with an archive's, keeping this installation's
    secrets, access token and `INSTALLATION_SETTINGS`. The restored queue is
    paused."""
    config = load_config()
    with maintenance.gate.exclusive():
        with _staged(archive, config.data_dir) as (staged, work):
            backup_store.prepare_restore(
                staged.db_path,
                staged.audio_dir,
                config.audio_dir,
                _installation_state(),
                database.page_size(),
            )
            _swap_in(staged, config, work)
    log.info("library_restored", documents=staged.summary.documents)
    return RestoreResult(**staged.summary.model_dump(), is_queue_paused=True)


@contextmanager
def _staged(archive: BinaryIO, data_dir: Path) -> Iterator[tuple[StagedLibrary, Path]]:
    with tempfile.TemporaryDirectory(dir=data_dir, prefix=RESTORE_PREFIX) as name:
        work = Path(name)
        try:
            staged = _unpack(archive, work)
        except (zipfile.BadZipFile, zlib.error, EOFError):
            raise InvalidBackupError(
                "The backup archive is damaged.", hint=DAMAGED_HINT, field="file"
            ) from None
        yield staged, work


def _unpack(archive: BinaryIO, work: Path) -> StagedLibrary:
    with zipfile.ZipFile(archive) as zip_file:
        members = _checked_members(zip_file)
        _check_free_space(work, members)
        manifest = _read_manifest(zip_file)
        staged_audio = work / SNAPSHOT_AUDIO_DIR
        create_private_dir(staged_audio)
        for member in members:
            _extract(zip_file, member, _target(member.filename, work))
    db_path = work / DATABASE_NAME
    schema_version = _check_database(db_path)
    counts = backup_store.count_library(db_path)
    summary = BackupSummary(
        app_version=manifest.app_version,
        created=manifest.created,
        schema_version=schema_version,
        documents=counts.documents,
        versions=counts.versions,
        audio=counts.audio,
        audio_files=len(members) - 2,
        queued_jobs=counts.queued_jobs,
    )
    return StagedLibrary(db_path, staged_audio, summary)


def _checked_members(zip_file: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = zip_file.infolist()
    names = [member.filename for member in members]
    if len(members) > MAX_MEMBERS or len(set(names)) != len(names):
        raise _not_a_backup("It holds too many or repeated files.")
    for name in names:
        if name not in (MANIFEST_NAME, DATABASE_NAME) and not AUDIO_MEMBER.fullmatch(
            name
        ):
            raise _not_a_backup(f"It holds an unexpected file: {name!r}.")
    for required in (MANIFEST_NAME, DATABASE_NAME):
        if required not in names:
            raise _not_a_backup(f"{required} is missing.")
    if sum(member.file_size for member in members) > MAX_UNPACKED_BYTES:
        raise _not_a_backup("It is larger than any library Phemius restores.")
    return members


def _check_free_space(work: Path, members: list[zipfile.ZipInfo]) -> None:
    needed = sum(member.file_size for member in members) + DISK_HEADROOM_BYTES
    if shutil.disk_usage(work).free < needed:
        raise InvalidBackupError(
            "There is not enough free disk space to restore this backup.",
            hint="Free up space in the library folder, then try again.",
            field="file",
        )


def _read_manifest(zip_file: zipfile.ZipFile) -> BackupManifest:
    if zip_file.getinfo(MANIFEST_NAME).file_size > MAX_MANIFEST_BYTES:
        raise _not_a_backup("Its manifest is too large.")
    try:
        raw = json.loads(zip_file.read(MANIFEST_NAME))
    except ValueError:
        raise _not_a_backup("Its manifest is not valid JSON.") from None
    if not isinstance(raw, dict) or raw.get("format") != FORMAT:
        raise _not_a_backup("Its manifest does not name the backup format.")
    version = raw.get("format_version")
    if isinstance(version, int) and version > FORMAT_VERSION:
        raise _made_by_newer_version()
    try:
        manifest = BackupManifest.model_validate(raw)
    except ValidationError:
        raise _not_a_backup("Its manifest is incomplete.") from None
    if manifest.format_version != FORMAT_VERSION:
        raise _not_a_backup("Its format version is unknown.")
    return manifest


def _target(name: str, work: Path) -> Path:
    if name in (MANIFEST_NAME, DATABASE_NAME):
        return work / name
    match = AUDIO_MEMBER.fullmatch(name)
    assert match is not None, "members are checked before extraction"
    return work / SNAPSHOT_AUDIO_DIR / match.group(1)


def _extract(zip_file: zipfile.ZipFile, member: zipfile.ZipInfo, target: Path) -> None:
    # Reading to the end checks the size and CRC the archive declares.
    create_private_file(target)
    with zip_file.open(member) as source, target.open("wb") as destination:
        shutil.copyfileobj(source, destination)


def _check_database(db_path: Path) -> int:
    try:
        schema_version = backup_store.read_schema_version(db_path)
    except sqlite3.DatabaseError:
        raise _not_a_backup("Its database is damaged.") from None
    if schema_version > len(MIGRATIONS):
        raise _made_by_newer_version()
    if schema_version < 1:
        raise _not_a_backup("Its database holds no library.")
    foreign = backup_store.foreign_schema_objects(db_path, schema_version)
    if foreign:
        raise _not_a_backup(
            f"Its database holds objects Phemius did not create: {', '.join(foreign)}."
        )
    return schema_version


def _installation_state() -> InstallationState:
    keys = [*secret_setting_keys(), *INSTALLATION_SETTINGS]
    saved = settings_store.read_settings()
    return InstallationState(
        settings={key: saved[key] for key in keys if key in saved},
        setting_keys=keys,
        token_hash=access_store.read_token_hash(),
        sources=sources.kept_sources(),
    )


def _swap_in(staged: StagedLibrary, config: Config, work: Path) -> None:
    previous_audio = work / "previous-audio"
    if config.audio_dir.exists():
        config.audio_dir.rename(previous_audio)
    staged.audio_dir.rename(config.audio_dir)
    try:
        database.replace_with(staged.db_path)
    except BaseException:
        config.audio_dir.rename(staged.audio_dir)
        if previous_audio.exists():
            previous_audio.rename(config.audio_dir)
        raise


def _not_a_backup(reason: str) -> InvalidBackupError:
    return InvalidBackupError(
        f"This is not a Phemius backup this version can restore. {reason}",
        hint=DAMAGED_HINT,
        field="file",
    )


def _made_by_newer_version() -> InvalidBackupError:
    return InvalidBackupError(
        "This backup was made by a newer version of Phemius.",
        hint="Upgrade Phemius, then restore the backup again.",
        field="file",
    )
