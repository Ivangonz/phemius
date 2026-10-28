from pathlib import Path

import pytest

from phemius.models.base import AudioSuitability
from phemius.store import database, document_list
from phemius.store import documents as document_store
from phemius.store import jobs as job_store
from phemius.store.document_list import DocumentFilters, DocumentListItem
from phemius.store.documents import NewDocument


@pytest.fixture(autouse=True)
def library(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")


def _add(
    title: str,
    category: str = "how-to",
    tone: str = "teacher",
    text: str | None = None,
    suitability: AudioSuitability = "recommended",
) -> int:
    stored = document_store.add_document(
        NewDocument(
            title=title,
            source=f"/docs/{title}.md",
            text=text or f"{title} text.",
            category=category,
            summary="A doc.",
            suggested_tone=tone,
            tone_rationale="Suits a doc.",
            audio_suitability=suitability,
            suitability_reason="Rated for the test.",
            suitability_source="model",
        )
    )
    return stored.document_id


def _enqueue(document_id: int) -> job_store.QueuedAudio:
    document = document_store.get_document(document_id)
    assert document is not None
    return job_store.enqueue_audio(
        document_id, document["version_id"], "teacher", "stub:silent"
    )


def _list(filters: DocumentFilters = DocumentFilters()) -> list[DocumentListItem]:
    return document_list.list_documents(filters).items


def _titles(items: list[DocumentListItem]) -> list[str]:
    return [item["title"] for item in items]


def test_each_filter_narrows_and_filters_combine() -> None:
    _add("Deploy", category="how-to", tone="teacher")
    _add("Roadmap", category="proposal / spec", tone="podcast")
    _add("Runbook", category="how-to", tone="podcast")

    how_to = DocumentFilters(category="how-to")
    podcast = DocumentFilters(tone="podcast")
    how_to_podcast = DocumentFilters(category="how-to", tone="podcast")

    assert _titles(_list(how_to)) == ["Runbook", "Deploy"]
    assert _titles(_list(podcast)) == ["Runbook", "Roadmap"]
    assert _titles(_list(how_to_podcast)) == ["Runbook"]
    assert _titles(_list(DocumentFilters(title_search="road"))) == ["Roadmap"]


def test_status_comes_from_the_latest_versions_newest_job() -> None:
    queued = _add("Queued")
    cancelled = _add("Cancelled")
    _add("Silent")
    _enqueue(queued)
    job_store.cancel_job(_enqueue(cancelled).job_id)

    statuses = {item["title"]: item["status"] for item in _list()}

    assert statuses == {
        "Queued": "queued",
        "Cancelled": "cancelled",
        "Silent": "no_audio",
    }
    assert _titles(_list(DocumentFilters(status="no_audio"))) == ["Silent"]
    assert _titles(_list(DocumentFilters(status="cancelled"))) == ["Cancelled"]


def test_newer_audio_of_the_latest_version_decides_the_status() -> None:
    document_id = _add("Guide")
    job_store.cancel_job(_enqueue(document_id).job_id)
    newest = _enqueue(document_id)

    [item] = _list()

    assert (item["status"], item["audio_id"]) == ("queued", newest.audio_id)


def test_audio_of_an_earlier_version_leaves_the_latest_without_audio() -> None:
    document_id = _add("Guide", text="Install with pip.")
    _enqueue(document_id)
    _add("Guide", text="Install with uv.")

    [item] = _list()

    assert (item["version"], item["status"]) == (2, "no_audio")
    assert item["audio_id"] is None
    assert item["is_changed"] is True


def test_each_row_shows_whether_its_latest_version_suits_audio() -> None:
    _add("Guide", text="Install with pip.")
    _add("Guide", text="| Code | Meaning |", suitability="not_recommended")
    _add("Notes", suitability="partial")

    suitability = {item["title"]: item["audio_suitability"] for item in _list()}

    assert suitability == {"Guide": "not_recommended", "Notes": "partial"}


def test_title_search_matches_percent_and_underscore_literally() -> None:
    _add("100% uptime")
    _add("1000 users")
    _add("snake_case")
    _add("snakeXcase")

    assert _titles(_list(DocumentFilters(title_search="0%"))) == ["100% uptime"]
    assert _titles(_list(DocumentFilters(title_search="e_c"))) == ["snake_case"]


def test_pages_slice_the_ordered_list_and_report_the_total() -> None:
    for title in ["A", "B", "C"]:
        _add(title)

    first = document_list.list_documents(limit=2, offset=0)
    second = document_list.list_documents(limit=2, offset=2)

    assert (_titles(first.items), _titles(second.items)) == (["C", "B"], ["A"])
    assert first.total == second.total == 3


def test_total_counts_only_matching_documents() -> None:
    _add("Deploy", category="how-to")
    _add("Roadmap", category="reference")

    page = document_list.list_documents(DocumentFilters(category="how-to"), limit=1)

    assert page.total == 1


def test_documents_can_be_ordered_by_title_and_update() -> None:
    _add("beta")
    _add("Alpha", text="First.")
    _add("Gamma")
    _add("Alpha", text="Second.")

    by_title = document_list.list_documents(order_by="title").items
    by_update = document_list.list_documents(order_by="-updated").items
    oldest_first = document_list.list_documents(order_by="created").items

    assert _titles(by_title) == ["Alpha", "beta", "Gamma"]
    assert _titles(by_update) == ["Alpha", "Gamma", "beta"]
    assert _titles(oldest_first) == ["beta", "Alpha", "Gamma"]


def test_signature_is_stable_until_a_visible_field_changes() -> None:
    document_id = _add("Guide")
    queued = _enqueue(document_id)

    [first] = _list()
    [again] = _list()
    job_store.cancel_job(queued.job_id)
    [cancelled] = _list()

    assert first["signature"] == again["signature"]
    assert cancelled["signature"] != first["signature"]


def test_finished_audio_reports_its_format_and_size() -> None:
    _add("Silent")
    queued = _enqueue(_add("Narrated"))
    claimed = job_store.claim_next("writing_script")
    assert claimed is not None
    job_store.finish_audio(
        claimed, job_store.AudioFile("/audio/1.m4a", "m4a", size_bytes=2048)
    )

    files = {
        item["title"]: (item["audio_id"], item["format"], item["size_bytes"])
        for item in _list()
    }

    assert files == {
        "Narrated": (queued.audio_id, "m4a", 2048),
        "Silent": (None, None, None),
    }
