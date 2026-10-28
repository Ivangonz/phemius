"""The library's document list: one summary row per document, filtered and paged.

A row describes the document's latest version and that version's newest audio.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, TypedDict, cast

from phemius.models.base import AudioSuitability
from phemius.store.database import transaction
from phemius.store.jobs import AudioFormat, JobStage, JobState

type DocumentStatus = JobState | Literal["no_audio"]
type DocumentOrder = Literal["-created", "created", "title", "-updated"]

_ORDER_CLAUSES: dict[DocumentOrder, str] = {
    "-created": "created DESC, id DESC",
    "created": "created, id",
    "title": "title COLLATE NOCASE, id",
    "-updated": "updated DESC, id DESC",
}

# `updated` is when the latest version was stored. `is_changed` marks a document
# whose earlier versions have audio while its latest version has none.
_SUMMARIES = """
WITH latest AS (
    SELECT d.id, d.source, d.created, v.id AS version_id, v.number AS version,
        v.title, v.category, v.suggested_tone, v.audio_suitability,
        v.created AS updated
    FROM docs d JOIN doc_versions v ON v.doc_id = d.id
    WHERE v.number = (SELECT MAX(number) FROM doc_versions WHERE doc_id = d.id)
),
summaries AS (
    SELECT l.id, l.title, l.source, l.category, l.suggested_tone,
        l.audio_suitability, l.version, l.created, l.updated, a.id AS audio_id,
        a.format, a.size_bytes,
        COALESCE(j.state, 'no_audio') AS status, j.stage,
        a.id IS NULL AND EXISTS (SELECT 1 FROM audio WHERE doc_id = l.id)
            AS is_changed
    FROM latest l
    LEFT JOIN audio a ON a.id = (
        SELECT id FROM audio WHERE version_id = l.version_id
        ORDER BY created DESC, id DESC LIMIT 1
    )
    LEFT JOIN jobs j ON j.audio_id = a.id
)
"""


class DocumentListItem(TypedDict):
    id: int
    title: str
    source: str
    category: str
    suggested_tone: str
    # None for versions imported before suitability was rated: unknown.
    audio_suitability: AudioSuitability | None
    version: int
    created: float
    updated: float
    audio_id: int | None
    format: AudioFormat | None
    size_bytes: int | None
    status: DocumentStatus
    stage: JobStage | None
    is_changed: bool
    # Changes only when another field changes, so a client can skip re-rendering.
    signature: str


@dataclass(frozen=True)
class DocumentFilters:
    category: str | None = None
    tone: str | None = None
    status: DocumentStatus | None = None
    title_search: str | None = None


@dataclass(frozen=True)
class DocumentListPage:
    items: list[DocumentListItem]
    total: int


def list_documents(
    filters: DocumentFilters = DocumentFilters(),
    order_by: DocumentOrder = "-created",
    limit: int = 25,
    offset: int = 0,
) -> DocumentListPage:
    """One page of document summaries matching every given filter."""
    where, parameters = _where_clause(filters)
    with transaction() as connection:
        total: int = connection.execute(
            f"{_SUMMARIES} SELECT COUNT(*) FROM summaries {where}", parameters
        ).fetchone()[0]
        rows = connection.execute(
            f"{_SUMMARIES} SELECT * FROM summaries {where}"
            f" ORDER BY {_ORDER_CLAUSES[order_by]} LIMIT ? OFFSET ?",
            [*parameters, limit, offset],
        ).fetchall()
    return DocumentListPage(items=[_item(dict(row)) for row in rows], total=total)


def _where_clause(filters: DocumentFilters) -> tuple[str, list[str]]:
    conditions: list[str] = []
    parameters: list[str] = []
    for column, value in [
        ("category", filters.category),
        ("suggested_tone", filters.tone),
        ("status", filters.status),
    ]:
        if value is not None:
            conditions.append(f"{column} = ?")
            parameters.append(value)
    if filters.title_search:
        conditions.append("title LIKE ? ESCAPE '\\'")
        parameters.append(f"%{_escape_like(filters.title_search)}%")
    return ("WHERE " + " AND ".join(conditions) if conditions else ""), parameters


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _item(row: dict[str, object]) -> DocumentListItem:
    row["is_changed"] = bool(row["is_changed"])
    row["signature"] = _signature(row)
    return cast(DocumentListItem, row)


def _signature(fields: dict[str, object]) -> str:
    visible = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(visible.encode()).hexdigest()[:16]
