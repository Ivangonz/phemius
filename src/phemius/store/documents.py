"""Documents in the library. Deduplicated by content hash."""

import hashlib
import time
from dataclasses import dataclass
from typing import TypedDict, cast

from phemius.store.audio import AudioSummary
from phemius.store.database import transaction


class DocumentSummary(TypedDict):
    id: int
    title: str
    source: str
    category: str
    summary: str
    suggested_tone: str
    created: float
    audio: list[AudioSummary]


class Document(TypedDict):
    id: int
    title: str
    source: str
    content_hash: str
    text: str
    category: str
    summary: str
    suggested_tone: str
    created: float


@dataclass(frozen=True)
class NewDocument:
    title: str
    source: str
    text: str
    category: str
    summary: str
    suggested_tone: str


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def add_document(document: NewDocument) -> tuple[int, bool]:
    """Insert a document. Returns `(document_id, is_created)`."""
    content_hash = hash_text(document.text)
    with transaction() as connection:
        existing = connection.execute(
            "SELECT id FROM docs WHERE content_hash = ?", (content_hash,)
        ).fetchone()
        if existing:
            return int(existing["id"]), False
        cursor = connection.execute(
            "INSERT INTO docs (title, source, content_hash, text, category, summary,"
            " suggested_tone, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                document.title,
                document.source,
                content_hash,
                document.text,
                document.category,
                document.summary,
                document.suggested_tone,
                time.time(),
            ),
        )
        return cast(int, cursor.lastrowid), True


def list_documents() -> list[DocumentSummary]:
    with transaction() as connection:
        documents = [
            dict(row)
            for row in connection.execute(
                "SELECT id, title, source, category, summary, suggested_tone, created"
                " FROM docs ORDER BY created DESC"
            )
        ]
        for document in documents:
            document["audio"] = [
                dict(row)
                for row in connection.execute(
                    "SELECT id, tone, voice, status, error FROM audio"
                    " WHERE doc_id = ? ORDER BY created DESC",
                    (document["id"],),
                )
            ]
    return cast(list[DocumentSummary], documents)


def get_document(document_id: int) -> Document | None:
    with transaction() as connection:
        row = connection.execute(
            "SELECT * FROM docs WHERE id = ?", (document_id,)
        ).fetchone()
    return cast(Document, dict(row)) if row else None
