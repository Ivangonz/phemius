import os
from pathlib import Path

import pytest

from phemius.errors import InvalidInputError, SourceError
from phemius.sources import folder
from phemius.sources.base import SourceItem


def _synced(source: folder.FolderSource) -> list[SourceItem]:
    items: list[SourceItem] = []
    source.sync(items.append)
    return sorted(items, key=lambda item: item.key)


def test_sync_finds_supported_files_in_subfolders(tmp_path: Path) -> None:
    (tmp_path / "guides").mkdir()
    (tmp_path / "guides" / "install.md").write_text("# Install")
    (tmp_path / "notes.txt").write_text("Notes")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / ".hidden.md").write_text("# Hidden")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "description.md").write_text("# Not a document")

    items = _synced(folder.from_config({"path": str(tmp_path)}))

    assert [(item.key, item.name) for item in items] == [
        (str(tmp_path / "guides" / "install.md"), "guides/install.md"),
        (str(tmp_path / "notes.txt"), "notes.txt"),
    ]
    assert all(item.path.is_file() for item in items)


def test_sync_of_a_missing_folder_raises_a_source_error(tmp_path: Path) -> None:
    source = folder.from_config({"path": str(tmp_path / "missing")})

    with pytest.raises(SourceError) as raised:
        source.sync(lambda item: None)

    assert raised.value.hint is not None


def test_an_event_path_through_a_symlink_keeps_the_configured_key(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    os.symlink(real, linked)
    source = folder.from_config({"path": str(linked)})

    item = source.item_at(real / "guide.md")

    assert item is not None
    assert item.key == str(linked / "guide.md")


def test_keys_start_with_the_key_prefix(tmp_path: Path) -> None:
    (tmp_path / "guide.md").write_text("# Guide")
    source = folder.from_config({"path": str(tmp_path)})

    [item] = _synced(source)

    assert item.key.startswith(source.key_prefix)


@pytest.mark.parametrize("config", [{}, {"path": "relative/docs"}, {"path": 3}])
def test_invalid_config_is_rejected(config: dict[str, object]) -> None:
    with pytest.raises(InvalidInputError):
        folder.from_config(config)


def test_home_folder_is_expanded() -> None:
    source = folder.from_config({"path": "~/docs"})

    assert source.config == {"path": str(Path.home() / "docs")}
