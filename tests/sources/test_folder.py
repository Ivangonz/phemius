import time
from pathlib import Path

import pytest

from phemius.sources.folder import import_existing_files, import_watched_file
from phemius.store import audio as audio_store
from phemius.store import database
from phemius.store import documents as document_store
from phemius.store.audio import Audio


@pytest.fixture
def watched(isolated_env: Path, tmp_path: Path) -> Path:
    database.init_database(isolated_env / "library.db")
    folder = tmp_path / "watched"
    folder.mkdir()
    return folder


def _wait_until_finished(audio_id: int) -> Audio:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        audio = audio_store.get_audio(audio_id)
        if audio and audio["status"] in {"done", "error"}:
            return audio
        time.sleep(0.05)
    raise AssertionError(f"audio {audio_id} did not finish")


def _import_with_audio(path: Path) -> Audio:
    import_watched_file(path, is_auto_audio=True)
    [document] = document_store.list_documents()
    return _wait_until_finished(document["audio"][0]["id"])


def test_existing_supported_files_are_imported(watched: Path) -> None:
    (watched / "guide.md").write_text("# Guide\n\nHow to install the tool.")
    (watched / ".hidden.md").write_text("# Hidden")
    (watched / "image.png").write_bytes(b"\x89PNG")

    import_existing_files(watched, is_auto_audio=False)

    titles = [document["title"] for document in document_store.list_documents()]
    assert titles == ["Guide"]


def test_editing_a_watched_file_adds_a_version_and_keeps_old_audio(
    watched: Path,
) -> None:
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    first_audio = _import_with_audio(guide)

    guide.write_text("# Guide\n\nInstall with uv.")
    import_watched_file(guide, is_auto_audio=True)

    [document] = document_store.list_documents()
    assert document["version"] == 2
    assert document["is_changed"] is True
    assert [audio["id"] for audio in document["audio"]] == [first_audio["id"]]
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

    [document] = document_store.list_documents()
    assert [audio["version"] for audio in document["audio"]] == [2, 1]
    assert new_audio["status"] == "done", new_audio["error"]
    assert document["is_changed"] is False


def test_saving_identical_content_adds_no_version_or_audio(watched: Path) -> None:
    guide = watched / "guide.md"
    guide.write_text("# Guide\n\nInstall with pip.")
    _import_with_audio(guide)

    import_watched_file(guide, is_auto_audio=True)

    [document] = document_store.list_documents()
    assert document["version"] == 1
    assert len(document["audio"]) == 1
