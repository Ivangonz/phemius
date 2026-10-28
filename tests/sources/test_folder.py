import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from phemius.services.runner import start_runner
from phemius.sources.folder import import_existing_files, import_watched_file
from phemius.store import audio as audio_store
from phemius.store import database, document_list
from phemius.store import documents as document_store
from phemius.store.audio import Audio
from phemius.store.document_list import DocumentListItem
from tests.models.fakes import FakeScriptModel, UseScriptModel


@pytest.fixture
def watched(isolated_env: Path, tmp_path: Path) -> Iterator[Path]:
    database.init_database(isolated_env / "library.db")
    folder = tmp_path / "watched"
    folder.mkdir()
    runner = start_runner()
    yield folder
    runner.stop()


def _wait_until_finished(audio_id: int) -> Audio:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        audio = audio_store.get_audio(audio_id)
        if audio and audio["status"] in {"done", "failed", "cancelled"}:
            return audio
        time.sleep(0.05)
    raise AssertionError(f"audio {audio_id} did not finish")


def _only_document() -> DocumentListItem:
    [document] = document_list.list_documents().items
    return document


def _audio_ids_by_version(document_id: int) -> dict[int, list[int]]:
    page = document_store.list_versions(document_id, limit=25, offset=0)
    assert page is not None
    return {
        version["number"]: [audio["id"] for audio in version["audio"]]
        for version in page.items
    }


def _import_with_audio(path: Path) -> Audio:
    import_watched_file(path, is_auto_audio=True)
    audio_id = _only_document()["audio_id"]
    assert audio_id is not None
    return _wait_until_finished(audio_id)


def test_existing_supported_files_are_imported(watched: Path) -> None:
    (watched / "guide.md").write_text("# Guide\n\nHow to install the tool.")
    (watched / ".hidden.md").write_text("# Hidden")
    (watched / "image.png").write_bytes(b"\x89PNG")

    import_existing_files(watched, is_auto_audio=False)

    titles = [document["title"] for document in document_list.list_documents().items]
    assert titles == ["Guide"]


def test_editing_a_watched_file_adds_a_version_and_keeps_old_audio(
    watched: Path,
) -> None:
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    first_audio = _import_with_audio(guide)

    guide.write_text("# Guide\n\nInstall with uv.")
    import_watched_file(guide, is_auto_audio=True)

    document = _only_document()
    assert (document["version"], document["status"]) == (2, "no_audio")
    assert document["is_changed"] is True
    assert _audio_ids_by_version(document["id"]) == {2: [], 1: [first_audio["id"]]}
    assert first_audio["path"] and Path(first_audio["path"]).exists()


def test_regenerate_setting_builds_audio_for_the_new_version(
    watched: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_WATCH_ON_CHANGE", "regenerate")
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    _import_with_audio(guide)

    guide.write_text("# Guide\n\nInstall with uv.")
    new_audio = _import_with_audio(guide)

    document = _only_document()
    assert document["audio_id"] == new_audio["id"]
    assert len(_audio_ids_by_version(document["id"])[1]) == 1
    assert new_audio["status"] == "done", new_audio["error"]
    assert document["is_changed"] is False


def test_saving_identical_content_adds_no_version_or_audio(watched: Path) -> None:
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    _import_with_audio(guide)

    import_watched_file(guide, is_auto_audio=True)

    document = _only_document()
    assert document["version"] == 1
    assert len(_audio_ids_by_version(document["id"])[1]) == 1


def test_only_changed_content_is_sent_to_the_model(
    watched: Path, use_script_model: UseScriptModel
) -> None:
    model = FakeScriptModel()
    use_script_model(model)
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    import_watched_file(guide, is_auto_audio=False)

    import_watched_file(guide, is_auto_audio=False)
    calls_after_unchanged_save = model.analyze_calls
    guide.write_text("# Guide\n\nInstall with uv.")
    import_watched_file(guide, is_auto_audio=False)

    assert calls_after_unchanged_save == 1
    assert model.analyze_calls == 2


def test_watched_document_not_recommended_is_imported_but_not_narrated(
    watched: Path, use_script_model: UseScriptModel
) -> None:
    use_script_model(FakeScriptModel(suitability="not_recommended"))
    reference = watched / "codes.md"
    reference.write_text("# Codes\n\n| Code | Meaning |\n| --- | --- |\n| 1 | One |")

    with capture_logs() as logs:
        import_watched_file(reference, is_auto_audio=True)

    [document] = document_list.list_documents().items
    assert document["status"] == "no_audio"
    assert document["audio_suitability"] == "not_recommended"
    [skipped] = [entry for entry in logs if entry["event"] == "auto_audio_skipped"]
    assert skipped["document_id"] == document["id"]
    assert "codes.md" not in str(skipped)
