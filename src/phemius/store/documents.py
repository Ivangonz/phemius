"""Documents in the library, identified by source, each with its versions.

A document's fields (title, text, category...) are those of its latest version.
"""

import hashlib
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Literal, TypedDict, cast

from phemius.models.base import AudioSuitability, SuitabilitySource
from phemius.store.audio import AUDIO_JOB_COLUMNS, AudioSummary, section_titles
from phemius.store.database import transaction
from phemius.store.sources import exclude_items

type SaveOutcome = Literal["created", "new_version", "unchanged"]
type DeleteOutcome = Literal["deleted", "missing", "job_running"]

# None for versions analyzed before suitability existed: unknown, not judged.
_SUITABILITY_COLUMNS = (
    "v.tone_rationale, v.audio_suitability, v.suitability_reason, v.suitability_source"
)


class Document(TypedDict):
    id: int
    version_id: int
    version: int
    title: str
    source: str
    # The managed source it came from; None for uploads and older imports.
    source_id: int | None
    content_hash: str
    text: str
    category: str
    summary: str
    suggested_tone: str
    tone_rationale: str | None
    audio_suitability: AudioSuitability | None
    suitability_reason: str | None
    suitability_source: SuitabilitySource | None
    created: float


class VersionSummary(TypedDict):
    id: int
    number: int
    title: str
    content_hash: str
    category: str
    summary: str
    suggested_tone: str
    tone_rationale: str | None
    audio_suitability: AudioSuitability | None
    suitability_reason: str | None
    suitability_source: SuitabilitySource | None
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
    tone_rationale: str
    audio_suitability: AudioSuitability
    suitability_reason: str
    suitability_source: SuitabilitySource
    source_id: int | None = None


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
            document_id = _insert_document(
                connection, document.source, document.source_id
            )
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


def _insert_document(
    connection: sqlite3.Connection, source: str, source_id: int | None
) -> int:
    cursor = connection.execute(
        "INSERT INTO docs (source, source_id, created) VALUES (?, ?, ?)",
        (source, source_id, time.time()),
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
        " category, summary, suggested_tone, tone_rationale, audio_suitability,"
        " suitability_reason, suitability_source, created)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            document_id,
            number,
            document.title,
            hash_text(document.text),
            document.text,
            document.category,
            document.summary,
            document.suggested_tone,
            document.tone_rationale,
            document.audio_suitability,
            document.suitability_reason,
            document.suitability_source,
            time.time(),
        ),
    )
    return StoredVersion(document_id, number, outcome)


def prune_earlier_versions(document_id: int) -> list[str]:
    """Delete every version but the latest, with its audio and jobs.

    A version with a running job is kept until a later prune: its worker is
    still writing to it. Returns the audio files to remove after this commits.
    """
    with transaction(is_immediate=True) as connection:
        rows = connection.execute(_PRUNABLE_VERSIONS, {"doc": document_id})
        version_ids = [row["id"] for row in rows]
        if not version_ids:
            return []
        marks = ", ".join("?" * len(version_ids))
        paths = connection.execute(
            f"SELECT path FROM audio WHERE version_id IN ({marks})"
            " AND path IS NOT NULL",
            version_ids,
        ).fetchall()
        connection.execute(
            f"DELETE FROM jobs WHERE version_id IN ({marks}) OR audio_id IN"
            f" (SELECT id FROM audio WHERE version_id IN ({marks}))",
            [*version_ids, *version_ids],
        )
        connection.execute(
            f"DELETE FROM audio WHERE version_id IN ({marks})", version_ids
        )
        connection.execute(
            f"DELETE FROM doc_versions WHERE id IN ({marks})", version_ids
        )
    return [row["path"] for row in paths]


_PRUNABLE_VERSIONS = """
SELECT v.id FROM doc_versions v
WHERE v.doc_id = :doc
    AND v.number < (SELECT MAX(number) FROM doc_versions WHERE doc_id = :doc)
    AND NOT EXISTS (
        SELECT 1 FROM audio a JOIN jobs j ON j.audio_id = a.id
        WHERE a.version_id = v.id AND j.state = 'running'
    )
"""


@dataclass(frozen=True)
class DeletedDocument:
    outcome: DeleteOutcome
    # Files to remove once the delete has committed.
    audio_paths: list[str] = field(default_factory=list)


_DOCUMENT_AUDIO = (
    "SELECT id FROM audio WHERE doc_id = :doc"
    " OR version_id IN (SELECT id FROM doc_versions WHERE doc_id = :doc)"
)
_DOCUMENT_JOBS = (
    f"FROM jobs WHERE (audio_id IN ({_DOCUMENT_AUDIO})"
    " OR version_id IN (SELECT id FROM doc_versions WHERE doc_id = :doc))"
)
_RUNNING_DOCUMENT_JOB = f"SELECT 1 {_DOCUMENT_JOBS} AND state = 'running' LIMIT 1"
_DELETE_DOCUMENT_STATEMENTS = [
    f"DELETE {_DOCUMENT_JOBS}",
    f"DELETE FROM audio WHERE id IN ({_DOCUMENT_AUDIO})",
    "DELETE FROM doc_versions WHERE doc_id = :doc",
    "DELETE FROM docs WHERE id = :doc",
]


def delete_document(document_id: int) -> DeletedDocument:
    """Delete a document with its versions, audio and jobs, unless one of its
    jobs is running.

    The running check shares the write lock with the delete, so no worker can
    claim a job in between. A document from a managed source is excluded from
    it in the same transaction, so the next sync does not import it again.
    """
    with transaction(is_immediate=True) as connection:
        document = connection.execute(
            "SELECT source, source_id FROM docs WHERE id = ?", (document_id,)
        ).fetchone()
        if document is None:
            return DeletedDocument("missing")
        parameters = {"doc": document_id}
        if connection.execute(_RUNNING_DOCUMENT_JOB, parameters).fetchone():
            return DeletedDocument("job_running")
        paths = connection.execute(
            f"SELECT path FROM audio WHERE id IN ({_DOCUMENT_AUDIO})"
            " AND path IS NOT NULL",
            parameters,
        ).fetchall()
        for statement in _DELETE_DOCUMENT_STATEMENTS:
            connection.execute(statement, parameters)
        if document["source_id"] is not None:
            exclude_items(connection, document["source_id"], [document["source"]])
    return DeletedDocument("deleted", [row["path"] for row in paths])


def _audio_summaries(
    connection: sqlite3.Connection, document_id: int
) -> list[AudioSummary]:
    rows = connection.execute(
        f"SELECT a.id, v.number AS version, a.tone, a.voice, {AUDIO_JOB_COLUMNS}"
        " FROM audio a JOIN jobs j ON j.audio_id = a.id"
        " LEFT JOIN doc_versions v ON v.id = a.version_id"
        " WHERE a.doc_id = ? ORDER BY a.created DESC, a.id DESC",
        (document_id,),
    ).fetchall()
    titles = section_titles(connection, [row["id"] for row in rows])
    return [
        cast(AudioSummary, {**dict(row), "section_titles": titles[row["id"]]})
        for row in rows
    ]


def get_document(document_id: int) -> Document | None:
    with transaction() as connection:
        row = connection.execute(
            "SELECT d.id, v.id AS version_id, v.number AS version, v.title,"
            " d.source, d.source_id, v.content_hash, v.text, v.category, v.summary,"
            f" v.suggested_tone, {_SUITABILITY_COLUMNS}, d.created"
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
            "SELECT v.id, v.number, v.title, v.content_hash, v.category, v.summary,"
            f" v.suggested_tone, {_SUITABILITY_COLUMNS}, v.created"
            " FROM doc_versions v WHERE v.doc_id = ?"
            " ORDER BY v.number DESC LIMIT ? OFFSET ?",
            (document_id, limit, offset),
        ).fetchall()
        audio = _audio_summaries(connection, document_id)
    items = [_version_summary(row, audio) for row in rows]
    return VersionPage(items=items, total=total)


def _version_summary(row: sqlite3.Row, audio: list[AudioSummary]) -> VersionSummary:
    version_audio = [item for item in audio if item["version"] == row["number"]]
    return cast(VersionSummary, {**dict(row), "audio": version_audio})
