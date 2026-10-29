import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from phemius.errors import DuplicateSourceError, NotFoundError, SettingLockedError
from phemius.services import pipeline, source_imports
from phemius.services import sources as source_service
from phemius.services.import_rules import ImportRules
from phemius.services.runner import start_runner
from phemius.services.sources import SourceChange
from phemius.sources import SourceItem
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


def _add_folder_with_rules(path: Path, **rules: object) -> int:
    path.mkdir(exist_ok=True)
    source = source_service.create_source(
        "folder", {"path": str(path)}, rules=ImportRules.model_validate(rules)
    )
    return source["id"]


def _activity(source_id: int | None = None) -> list[tuple[str, str | None, str]]:
    page = source_store.list_activity(source_id, limit=25, offset=0)
    return [(entry["action"], entry["item"], entry["detail"]) for entry in page.items]


def _item(folder: Path, name: str) -> SourceItem:
    return SourceItem(str(folder / name), name, folder / name)


def test_pausing_stops_imports_until_resumed(watched: Path) -> None:
    source_id = _add_folder(watched)
    (watched / "guide.md").write_text("# Guide\n\nInstall it.")
    paused = source_service.pause_source(source_id)

    source_service.sync_source(source_id)
    source_imports.import_item(source_id, _item(watched, "guide.md"))
    titles_while_paused = _titles()
    source_service.resume_source(source_id)
    source_service.sync_source(source_id)

    assert paused["status"] == "paused"
    assert titles_while_paused == []
    assert _titles() == ["Guide"]


def test_auto_generate_off_imports_without_audio(watched: Path) -> None:
    source_id = _add_folder_with_rules(watched, auto_audio=False)
    (watched / "guide.md").write_text("# Guide\n\nInstall it.")

    source_service.sync_source(source_id)

    assert _only_document()["status"] == "no_audio"
    assert _activity(source_id) == [
        ("imported", "guide.md", "Auto-generate is off for this source.")
    ]


def test_a_source_can_narrate_documents_the_global_rule_skips(
    watched: Path, use_script_model: UseScriptModel
) -> None:
    use_script_model(FakeScriptModel(suitability="not_recommended"))
    source_id = _add_folder_with_rules(watched, skip_not_recommended=False)
    (watched / "codes.md").write_text("# Codes\n\n| Code | Meaning |")

    source_service.sync_source(source_id)

    assert _only_document()["audio_id"] is not None
    assert _activity(source_id)[0][0] == "imported"


def test_a_skipped_not_recommended_document_is_logged_with_its_reason(
    watched: Path, use_script_model: UseScriptModel
) -> None:
    use_script_model(FakeScriptModel(suitability="not_recommended"))
    source_id = _add_folder(watched)
    (watched / "codes.md").write_text("# Codes\n\n| Code | Meaning |")

    source_service.sync_source(source_id)

    [(action, item, detail)] = _activity(source_id)
    assert (action, item) == ("skipped", "codes.md")
    assert "not recommended" in detail


def test_file_types_the_rules_leave_out_are_skipped_once(watched: Path) -> None:
    source_id = _add_folder_with_rules(watched, file_types=[".md"], auto_audio=False)
    (watched / "guide.md").write_text("# Guide\n\nInstall it.")
    (watched / "notes.txt").write_text("Notes.")

    source_service.sync_source(source_id)
    source_service.sync_source(source_id)

    assert _titles() == ["Guide"]
    assert sorted(_activity(source_id)) == [
        ("imported", "guide.md", "Auto-generate is off for this source."),
        ("skipped", "notes.txt", ".txt files are not imported from this source."),
    ]


def test_regenerate_rule_wins_over_the_global_mark_setting(watched: Path) -> None:
    source_id = _add_folder_with_rules(watched, regenerate_on_change=True)
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    _sync_with_audio(source_id)

    guide.write_text("# Guide\n\nInstall with uv.")
    new_audio = _sync_with_audio(source_id)

    assert _audio_ids_by_version(_only_document()["id"])[2] == [new_audio["id"]]
    assert _activity(source_id)[0] == ("updated", "guide.md", "Audio queued.")


def test_without_keep_versions_earlier_versions_and_their_audio_go(
    watched: Path,
) -> None:
    source_id = _add_folder_with_rules(watched, keep_versions=False)
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    first_audio = _sync_with_audio(source_id)

    guide.write_text("# Guide\n\nInstall with uv.")
    source_service.sync_source(source_id)

    document = _only_document()
    assert _audio_ids_by_version(document["id"]) == {2: []}
    assert first_audio["path"] and not Path(first_audio["path"]).exists()
    assert audio_store.get_audio(first_audio["id"]) is None


def test_a_failed_item_and_a_failed_sync_are_logged_once(
    library: None, tmp_path: Path
) -> None:
    source_id = _add_folder(tmp_path / "docs")
    (tmp_path / "docs" / "empty.md").write_text("   ")
    source_service.sync_source(source_id)
    source_service.sync_source(source_id)
    (tmp_path / "docs" / "empty.md").unlink()
    (tmp_path / "docs").rmdir()
    source_service.sync_source(source_id)
    source_service.sync_source(source_id)

    failures = _activity(source_id)
    assert [(action, item) for action, item, _ in failures] == [
        ("failed", None),
        ("failed", "empty.md"),
    ]
    assert "No text found" in failures[1][2]


def test_activity_lists_every_source_newest_first(
    library: None, tmp_path: Path
) -> None:
    first = _add_folder_with_rules(tmp_path / "first", auto_audio=False)
    second = _add_folder_with_rules(tmp_path / "second", auto_audio=False)
    (tmp_path / "first" / "deploy.md").write_text("# Deploy\n\nShip it.")
    (tmp_path / "second" / "notes.md").write_text("# Notes\n\nRecap.")
    source_service.sync_source(first)
    source_service.sync_source(second)

    page = source_store.list_activity(None, limit=1, offset=0)

    assert page.total == 2
    [entry] = page.items
    assert (entry["source_id"], entry["source_name"], entry["item"]) == (
        second,
        "second",
        "notes.md",
    )
    assert entry["document_id"] is not None


def test_editing_a_source_renames_it_and_merges_its_rules(
    library: None, tmp_path: Path
) -> None:
    source_id = _add_folder_with_rules(tmp_path / "docs", auto_audio=False)
    change = SourceChange.model_validate(
        {"name": "Team docs", "rules": {"file_types": ["md"]}}
    )

    edited = source_service.update_source(source_id, change)

    assert edited["name"] == "Team docs"
    assert edited["rules"] == {"auto_audio": False, "file_types": [".md"]}


def test_moving_a_source_onto_another_ones_folder_is_refused(
    library: None, tmp_path: Path
) -> None:
    _add_folder(tmp_path / "first")
    second = _add_folder(tmp_path / "second")
    change = SourceChange(config={"path": str(tmp_path / "first")})

    with pytest.raises(DuplicateSourceError):
        source_service.update_source(second, change)


def test_the_environment_folder_cannot_be_moved_or_deleted(
    library: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_WATCH_DIR", str(tmp_path / "env"))
    source_service.adopt_watch_folder()
    [source] = source_store.all_sources()
    move = SourceChange(config={"path": str(tmp_path / "elsewhere")})

    with pytest.raises(SettingLockedError):
        source_service.update_source(source["id"], move)
    with pytest.raises(SettingLockedError):
        source_service.delete_source(source["id"])
    renamed = source_service.update_source(source["id"], SourceChange(name="Docs"))

    assert renamed["name"] == "Docs"


def test_deleting_a_source_keeps_its_documents(watched: Path) -> None:
    source_id = _add_folder_with_rules(watched, auto_audio=False)
    (watched / "guide.md").write_text("# Guide\n\nInstall it.")
    source_service.sync_source(source_id)

    source_service.delete_source(source_id)

    document = document_store.get_document(_only_document()["id"])
    assert document is not None and document["source_id"] is None
    assert source_store.get_source(source_id) is None
    assert _activity() == []


def test_unknown_sources_raise_not_found(library: None) -> None:
    with pytest.raises(NotFoundError):
        source_service.pause_source(404)
    with pytest.raises(NotFoundError):
        source_service.delete_source(404)


def test_watchers_follow_sources_as_they_change(library: None, tmp_path: Path) -> None:
    source_service.start_sources()
    try:
        source_id = _add_folder_with_rules(tmp_path / "docs", auto_audio=False)
        is_watched_when_added = source_service.is_watching(source_id)
        source_service.pause_source(source_id)
        is_watched_when_paused = source_service.is_watching(source_id)
        source_service.resume_source(source_id)
        is_watched_when_resumed = source_service.is_watching(source_id)
        source_service.delete_source(source_id)

        assert (
            is_watched_when_added,
            is_watched_when_paused,
            is_watched_when_resumed,
        ) == (True, False, True)
        assert source_service.is_watching(source_id) is False
    finally:
        source_service.stop_sources()
