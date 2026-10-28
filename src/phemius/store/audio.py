"""Generated audio for a document: one row per tone and voice combination."""

import time
from typing import Literal, TypedDict, cast

from phemius.store.database import transaction

type AudioStatus = Literal["pending", "scripting", "synthesizing", "done", "error"]


class AudioSummary(TypedDict):
    id: int
    version: int | None
    tone: str
    voice: str | None
    status: AudioStatus
    error: str | None


class Audio(TypedDict):
    id: int
    doc_id: int
    version_id: int | None
    tone: str
    voice: str | None
    script: str | None
    path: str | None
    status: AudioStatus
    error: str | None
    created: float


def create_audio(document_id: int, version_id: int, tone: str, voice: str) -> int:
    with transaction() as connection:
        cursor = connection.execute(
            "INSERT INTO audio (doc_id, version_id, tone, voice, status, created)"
            " VALUES (?, ?, ?, ?, 'pending', ?)",
            (document_id, version_id, tone, voice, time.time()),
        )
        return cast(int, cursor.lastrowid)


def get_audio(audio_id: int) -> Audio | None:
    with transaction() as connection:
        row = connection.execute(
            "SELECT * FROM audio WHERE id = ?", (audio_id,)
        ).fetchone()
    return cast(Audio, dict(row)) if row else None


def mark_scripting(audio_id: int) -> None:
    _execute("UPDATE audio SET status = 'scripting' WHERE id = ?", audio_id)


def save_script(audio_id: int, script: str) -> None:
    _execute(
        "UPDATE audio SET script = ?, status = 'synthesizing' WHERE id = ?",
        script,
        audio_id,
    )


def mark_done(audio_id: int, path: str) -> None:
    _execute(
        "UPDATE audio SET path = ?, status = 'done', error = NULL WHERE id = ?",
        path,
        audio_id,
    )


def mark_failed(audio_id: int, error: str) -> None:
    _execute(
        "UPDATE audio SET status = 'error', error = ? WHERE id = ?", error, audio_id
    )


def _execute(sql: str, *parameters: object) -> None:
    with transaction() as connection:
        connection.execute(sql, parameters)
