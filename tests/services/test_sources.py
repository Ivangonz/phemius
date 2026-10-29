import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from phemius.errors import DuplicateSourceError
from phemius.services import pipeline
from phemius.services import sources as source_service
from phemius.services.runner import start_runner
from phemius.store import audio as audio_store
from phemius.store import database, document_list
from phemius.store import documents as document_store
from phemius.store import settings as settings_store
from phemius.store import sources as source_store
from phemius.store.audio import Audio
from phemius.store.document_list import DocumentListItem
from phemius.store.sources import StoredSource
from tests.models.fakes import FakeScriptModel, UseScriptModel


@pytest.fixture
def library(isolated_env: Path) -> Iterator[None]:
    database.init_database(isolated_env / "library.db")
    runner = start_runner()
    yield
    runner.stop()


@pytest.fixture
def watched(library: None, tmp_path: Path) -> Path:
    folder = tmp_path / "watched"
    folder.mkdir()
    return folder


def _add_folder(path: Path) -> int:
    path.mkdir(exist_ok=True)
    return source_service.create_source("folder", {"path": str(path)})["id"]


def _get_source(source_id: int) -> StoredSource:
    source = source_store.get_source(source_id)
    assert source is not None
    return source


def _titles() -> list[str]:
    return sorted(
        document["title"] for document in document_list.list_documents().items
    )


def _only_document() -> DocumentListItem:
    [document] = document_list.list_documents().items
    return document


def _wait_until_finished(audio_id: int) -> Audio:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        audio = audio_store.get_audio(audio_id)
        if audio and audio["status"] in {"done", "failed", "cancelled"}:
            return audio
        time.sleep(0.05)
    raise AssertionError(f"audio {audio_id} did not finish")


def _audio_ids_by_version(document_id: int) -> dict[int, list[int]]:
    page = document_store.list_versions(document_id, limit=25, offset=0)
    assert page is not None
    return {
        version["number"]: [audio["id"] for audio in version["audio"]]
        for version in page.items
    }


def _sync_with_audio(source_id: int) -> Audio:
    source_service.sync_source(source_id)
    audio_id = _only_document()["audio_id"]
    assert audio_id is not None
    return _wait_until_finished(audio_id)


def test_two_folders_sync_independently(library: None, tmp_path: Path) -> None:
    first = _add_folder(tmp_path / "first")
    second = _add_folder(tmp_path / "second")
    (tmp_path / "first" / "deploy.md").write_text("# Deploy\n\nShip it.")
    (tmp_path / "second" / "notes.md").write_text("# Notes\n\nRecap.")

    source_service.sync_source(first)
    titles_after_first = _titles()
    source_service.sync_source(second)

    assert titles_after_first == ["Deploy"]
    assert _titles() == ["Deploy", "Notes"]
    assert _get_source(first)["last_sync"] is not None


def test_documents_record_the_source_they_came_from(
    library: None, tmp_path: Path
) -> None:
    first = _add_folder(tmp_path / "first")
    second = _add_folder(tmp_path / "second")
    (tmp_path / "first" / "deploy.md").write_text("# Deploy\n\nShip it.")
    (tmp_path / "second" / "notes.md").write_text("# Notes\n\nRecap.")

    source_service.sync_source(first)
    source_service.sync_source(second)

    source_ids = {
        document["title"]: document_store.get_document(document["id"])
        for document in document_list.list_documents().items
    }
    assert {title: doc and doc["source_id"] for title, doc in source_ids.items()} == {
        "Deploy": first,
        "Notes": second,
    }


def test_a_missing_folder_records_the_error_on_its_source(
    library: None, tmp_path: Path
) -> None:
    source_id = _add_folder(tmp_path / "gone")
    (tmp_path / "gone").rmdir()

    source_service.sync_source(source_id)

    source = _get_source(source_id)
    assert source["error"] is not None
    assert source["last_sync"] is None


def test_a_later_good_sync_clears_the_error(library: None, tmp_path: Path) -> None:
    source_id = _add_folder(tmp_path / "flaky")
    (tmp_path / "flaky").rmdir()
    source_service.sync_source(source_id)

    (tmp_path / "flaky").mkdir()
    source_service.sync_source(source_id)

    assert _get_source(source_id)["error"] is None


def test_the_same_folder_cannot_be_added_twice(library: None, tmp_path: Path) -> None:
    _add_folder(tmp_path / "docs")

    with pytest.raises(DuplicateSourceError):
        _add_folder(tmp_path / "docs")


def test_env_watch_folder_becomes_a_source_once(
    library: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "listen"
    monkeypatch.setenv("PHEMIUS_WATCH_DIR", str(folder))

    source_service.adopt_watch_folder()
    source_service.adopt_watch_folder()

    [source] = source_store.all_sources()
    assert (source["kind"], source["name"], source["config"]) == (
        "folder",
        "listen",
        {"path": str(folder)},
    )


def test_saved_watch_folder_becomes_a_source_and_the_setting_is_removed(
    library: None, tmp_path: Path
) -> None:
    settings_store.save_settings({"watch_dir": str(tmp_path / "saved")})

    source_service.adopt_watch_folder()
    source_service.adopt_watch_folder()

    [source] = source_store.all_sources()
    assert source["config"] == {"path": str(tmp_path / "saved")}
    assert "watch_dir" not in settings_store.read_settings()


def test_env_watch_folder_wins_over_the_saved_one(
    library: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_store.save_settings({"watch_dir": str(tmp_path / "saved")})
    monkeypatch.setenv("PHEMIUS_WATCH_DIR", str(tmp_path / "env"))

    source_service.adopt_watch_folder()

    [source] = source_store.all_sources()
    assert source["config"] == {"path": str(tmp_path / "env")}
    assert settings_store.read_settings()["watch_dir"] == str(tmp_path / "saved")


def test_documents_already_imported_from_the_folder_join_its_source(
    library: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "listen"
    folder.mkdir()
    (folder / "guide.md").write_text("# Guide\n\nInstall it.")
    (tmp_path / "upload.md").write_text("# Upload\n\nNot in the folder.")
    inside = pipeline.import_file(folder / "guide.md")
    outside = pipeline.import_file(tmp_path / "upload.md")
    monkeypatch.setenv("PHEMIUS_WATCH_DIR", str(folder))

    source_service.adopt_watch_folder()

    [source] = source_store.all_sources()
    linked = document_store.get_document(inside.document_id)
    unlinked = document_store.get_document(outside.document_id)
    assert linked is not None and unlinked is not None
    assert (linked["source_id"], unlinked["source_id"]) == (source["id"], None)


def test_editing_a_watched_file_adds_a_version_and_keeps_old_audio(
    watched: Path,
) -> None:
    source_id = _add_folder(watched)
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    first_audio = _sync_with_audio(source_id)

    guide.write_text("# Guide\n\nInstall with uv.")
    source_service.sync_source(source_id)

    document = _only_document()
    assert (document["version"], document["status"]) == (2, "no_audio")
    assert document["is_changed"] is True
    assert _audio_ids_by_version(document["id"]) == {2: [], 1: [first_audio["id"]]}
    assert first_audio["path"] and Path(first_audio["path"]).exists()


def test_regenerate_setting_builds_audio_for_the_new_version(
    watched: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_WATCH_ON_CHANGE", "regenerate")
    source_id = _add_folder(watched)
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    _sync_with_audio(source_id)

    guide.write_text("# Guide\n\nInstall with uv.")
    new_audio = _sync_with_audio(source_id)

    document = _only_document()
    assert document["audio_id"] == new_audio["id"]
    assert len(_audio_ids_by_version(document["id"])[1]) == 1
    assert new_audio["status"] == "done", new_audio["error"]
    assert document["is_changed"] is False


def test_saving_identical_content_adds_no_version_or_audio(watched: Path) -> None:
    source_id = _add_folder(watched)
    (watched / "guide.md").write_text("# Guide\n\nInstall with pip.")
    _sync_with_audio(source_id)

    source_service.sync_source(source_id)

    document = _only_document()
    assert document["version"] == 1
    assert len(_audio_ids_by_version(document["id"])[1]) == 1


def test_only_changed_content_is_sent_to_the_model(
    watched: Path, use_script_model: UseScriptModel
) -> None:
    model = FakeScriptModel()
    use_script_model(model)
    source_id = _add_folder(watched)
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    source_service.sync_source(source_id)

    source_service.sync_source(source_id)
    calls_after_unchanged_save = model.analyze_calls
    guide.write_text("# Guide\n\nInstall with uv.")
    source_service.sync_source(source_id)

    assert calls_after_unchanged_save == 1
    assert model.analyze_calls == 2


def test_watched_document_not_recommended_is_imported_but_not_narrated(
    watched: Path, use_script_model: UseScriptModel
) -> None:
    use_script_model(FakeScriptModel(suitability="not_recommended"))
    source_id = _add_folder(watched)
    (watched / "codes.md").write_text(
        "# Codes\n\n| Code | Meaning |\n| --- | --- |\n| 1 | One |"
    )

    with capture_logs() as logs:
        source_service.sync_source(source_id)

    document = _only_document()
    assert document["status"] == "no_audio"
    assert document["audio_suitability"] == "not_recommended"
    [skipped] = [entry for entry in logs if entry["event"] == "auto_audio_skipped"]
    assert skipped["document_id"] == document["id"]
    assert "codes.md" not in str(skipped)


def test_one_unreadable_file_does_not_stop_the_sync(watched: Path) -> None:
    source_id = _add_folder(watched)
    (watched / "empty.md").write_text("   ")
    (watched / "guide.md").write_text("# Guide\n\nInstall it.")

    source_service.sync_source(source_id)

    assert _titles() == ["Guide"]
    assert _get_source(source_id)["error"] is None
