"""Documents in the library, identified by source, each with its versions.

A document's fields (title, text, category...) are those of its latest version.
"""

import hashlib
import sqlite3
import time
from dataclasses import dataclass
from typing import Literal, TypedDict, cast

from phemius.store.audio import AUDIO_JOB_COLUMNS, AudioSummary
from phemius.store.database import transaction

type SaveOutcome = Literal["created", "new_version", "unchanged"]


class Document(TypedDict):
    id: int
    version_id: int
    version: int
    title: str
    source: str
    content_hash: str
    text: str
    category: str
    summary: str
    suggested_tone: str
    created: float


class VersionSummary(TypedDict):
    id: int
    number: int
    title: str
    content_hash: str
    category: str
    summary: str
    suggested_tone: str
    created: float
    audio: list[AudioSummary]


@dataclass(frozen=True)
class VersionPage:
    items: list[VersionSummary]
    total: int


@dataclass(frozen=True)
class NewDocument:
    title: str
    source: str
    text: str
    category: str
    summary: str
    suggested_tone: str


@dataclass(frozen=True)
class StoredVersion:
    document_id: int
    version: int
    outcome: SaveOutcome


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def add_document(document: NewDocument) -> StoredVersion:
    """Store a new document, or a new version when its source's text changed."""
    content_hash = hash_text(document.text)
    with transaction(is_immediate=True) as connection:
        latest = _latest_version_from_source(connection, document.source)
        if latest is None:
            document_id = _insert_document(connection, document.source)
            return _insert_version(connection, document_id, 1, document, "created")
        if latest["content_hash"] == content_hash:
            return StoredVersion(latest["doc_id"], latest["number"], "unchanged")
        return _insert_version(
            connection, latest["doc_id"], latest["number"] + 1, document, "new_version"
        )


def find_unchanged(source: str, text: str) -> StoredVersion | None:
    """The latest version from `source` if its text is `text`, else None.

    A cheap pre-check only; `add_document` decides again under the write lock.
    """
    with transaction() as connection:
        latest = _latest_version_from_source(connection, source)
    if latest is None or latest["content_hash"] != hash_text(text):
        return None
    return StoredVersion(latest["doc_id"], latest["number"], "unchanged")


def _latest_version_from_source(
    connection: sqlite3.Connection, source: str
) -> sqlite3.Row | None:
    # Older libraries can hold several documents per source; the newest wins.
    row: sqlite3.Row | None = connection.execute(
        "SELECT v.doc_id, v.number, v.content_hash"
        " FROM docs d JOIN doc_versions v ON v.doc_id = d.id"
        " WHERE d.source = ? ORDER BY d.id DESC, v.number DESC LIMIT 1",
        (source,),
    ).fetchone()
    return row


def _insert_document(connection: sqlite3.Connection, source: str) -> int:
    cursor = connection.execute(
        "INSERT INTO docs (source, created) VALUES (?, ?)", (source, time.time())
    )
    return cast(int, cursor.lastrowid)


def _insert_version(
    connection: sqlite3.Connection,
    document_id: int,
    number: int,
    document: NewDocument,
    outcome: SaveOutcome,
) -> StoredVersion:
    connection.execute(
        "INSERT INTO doc_versions (doc_id, number, title, content_hash, text,"
        " category, summary, suggested_tone, created)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            document_id,
            number,
            document.title,
            hash_text(document.text),
            document.text,
            document.category,
            document.summary,
            document.suggested_tone,
            time.time(),
        ),
    )
    return StoredVersion(document_id, number, outcome)


def _audio_summaries(
    connection: sqlite3.Connection, document_id: int
) -> list[AudioSummary]:
    rows = connection.execute(
        f"SELECT a.id, v.number AS version, a.tone, a.voice, {AUDIO_JOB_COLUMNS}"
        " FROM audio a JOIN jobs j ON j.audio_id = a.id"
        " LEFT JOIN doc_versions v ON v.id = a.version_id"
        " WHERE a.doc_id = ? ORDER BY a.created DESC, a.id DESC",
        (document_id,),
    )
    return [cast(AudioSummary, dict(row)) for row in rows]


def get_document(document_id: int) -> Document | None:
    with transaction() as connection:
        row = connection.execute(
            "SELECT d.id, v.id AS version_id, v.number AS version, v.title,"
            " d.source, v.content_hash, v.text, v.category, v.summary,"
            " v.suggested_tone, d.created"
            " FROM docs d JOIN doc_versions v ON v.doc_id = d.id"
            " WHERE d.id = ? ORDER BY v.number DESC LIMIT 1",
            (document_id,),
        ).fetchone()
    return cast(Document, dict(row)) if row else None


def list_versions(document_id: int, limit: int, offset: int) -> VersionPage | None:
    """One page of a document's versions, newest first. None if it is missing."""
    with transaction() as connection:
        total: int = connection.execute(
            "SELECT COUNT(*) FROM doc_versions WHERE doc_id = ?", (document_id,)
        ).fetchone()[0]
        if total == 0:
            return None
        rows = connection.execute(
            "SELECT id, number, title, content_hash, category, summary,"
            " suggested_tone, created FROM doc_versions WHERE doc_id = ?"
            " ORDER BY number DESC LIMIT ? OFFSET ?",
            (document_id, limit, offset),
        ).fetchall()
        audio = _audio_summaries(connection, document_id)
    items = [_version_summary(row, audio) for row in rows]
    return VersionPage(items=items, total=total)


def _version_summary(row: sqlite3.Row, audio: list[AudioSummary]) -> VersionSummary:
    version_audio = [item for item in audio if item["version"] == row["number"]]
    return cast(VersionSummary, {**dict(row), "audio": version_audio})
