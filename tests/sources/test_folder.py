from pathlib import Path

from phemius.sources.folder import import_existing_files
from phemius.store import database
from phemius.store import documents as document_store


def test_existing_supported_files_are_imported(
    isolated_env: Path, tmp_path: Path
) -> None:
    database.init_database(isolated_env / "library.db")
    folder = tmp_path / "watched"
    folder.mkdir()
    (folder / "guide.md").write_text("# Guide\n\nHow to install the tool.")
    (folder / ".hidden.md").write_text("# Hidden")
    (folder / "image.png").write_bytes(b"\x89PNG")

    import_existing_files(folder, is_auto_audio=False)

    titles = [document["title"] for document in document_store.list_documents()]
    assert titles == ["Guide"]
