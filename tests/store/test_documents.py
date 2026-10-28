from pathlib import Path

import pytest

from phemius.store import audio as audio_store
from phemius.store import database
from phemius.store import documents as document_store
from phemius.store.documents import NewDocument


@pytest.fixture(autouse=True)
def library(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")


def _document(text: str, source: str = "/docs/guide.md") -> NewDocument:
    return NewDocument(
        title=text.split(".")[0],
        source=source,
        text=text,
        category="how-to",
        summary="A guide.",
        suggested_tone="teacher",
    )


def test_changed_content_from_the_same_source_adds_a_version() -> None:
    first = document_store.add_document(_document("Install it."))

    second = document_store.add_document(_document("Install it with uv."))

    assert (first.outcome, second.outcome) == ("created", "new_version")
    assert second.document_id == first.document_id
    assert (first.version, second.version) == (1, 2)
    document = document_store.get_document(first.document_id)
    assert document is not None
    assert (document["version"], document["text"]) == (2, "Install it with uv.")


def test_identical_content_does_not_create_a_version() -> None:
    first = document_store.add_document(_document("Install it."))

    again = document_store.add_document(_document("Install it."))

    assert again.outcome == "unchanged"
    assert (again.document_id, again.version) == (first.document_id, 1)
    page = document_store.list_versions(first.document_id, limit=25, offset=0)
    assert page is not None and page.total == 1


def test_another_source_is_another_document() -> None:
    first = document_store.add_document(_document("Install it.", source="a.md"))

    other = document_store.add_document(_document("Install it.", source="b.md"))

    assert other.outcome == "created"
    assert other.document_id != first.document_id


def test_new_version_keeps_earlier_audio_and_marks_document_changed() -> None:
    first = document_store.add_document(_document("Install it."))
    document = document_store.get_document(first.document_id)
    assert document is not None
    audio_id = audio_store.create_audio(
        first.document_id, document["version_id"], "teacher", "stub:silent"
    )
    audio_store.mark_done(audio_id, "/audio/1.wav")

    document_store.add_document(_document("Install it with uv."))

    [summary] = document_store.list_documents()
    assert summary["version"] == 2
    assert summary["is_changed"] is True
    assert [(item["id"], item["version"]) for item in summary["audio"]] == [
        (audio_id, 1)
    ]


def test_list_versions_pages_newest_first_with_their_audio() -> None:
    for text in ["One.", "Two.", "Three."]:
        stored = document_store.add_document(_document(text))
    document = document_store.get_document(stored.document_id)
    assert document is not None
    audio_id = audio_store.create_audio(
        stored.document_id, document["version_id"], "teacher", "stub:silent"
    )

    page = document_store.list_versions(stored.document_id, limit=2, offset=0)
    rest = document_store.list_versions(stored.document_id, limit=2, offset=2)

    assert page is not None and rest is not None
    assert [version["number"] for version in page.items] == [3, 2]
    assert [audio["id"] for audio in page.items[0]["audio"]] == [audio_id]
    assert page.items[1]["audio"] == []
    assert [version["title"] for version in rest.items] == ["One"]
    assert page.total == rest.total == 3


def test_list_versions_of_missing_document_is_none() -> None:
    assert document_store.list_versions(999, limit=25, offset=0) is None
