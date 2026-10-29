"""The `Source` protocol every source kind (folder, later GitHub, Confluence) meets.

A source only finds documents. Import rules, the library and the activity log
belong to `services/sources.py`, so every kind behaves the same.
"""

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SourceItem:
    """One document a source holds, readable from a local file.

    `key` identifies the document in the library (`docs.source`), so it must stay
    the same across syncs: a path for a folder, a URL for a repository.
    """

    key: str
    name: str
    path: Path


# Called once per item; the item's file is only valid during the call, so a
# remote source can download it to a temporary file.
type ItemHandler = Callable[[SourceItem], None]


class Watcher(Protocol):
    def stop(self) -> None:
        """Stop handing over items, without waiting for one being handled."""
        ...

    def join(self) -> None:
        """Wait, after `stop`, until no item is being handled."""
        ...


class Source(Protocol):
    @property
    def config(self) -> Mapping[str, object]:
        """The validated config, stored as the source's identity."""
        ...

    @property
    def default_name(self) -> str:
        """The name a source gets when the user gives none."""
        ...

    @property
    def key_prefix(self) -> str:
        """The start of every key this source gives its items."""
        ...

    def check(self) -> None:
        """Raise `SourceError` with a hint when the source cannot be read."""
        ...

    def sync(self, handle: ItemHandler, stop: threading.Event) -> None:
        """Hand every item the source holds now to `handle`.

        Returns early, between items, once `stop` is set: shutdown, pause and
        delete set it. Raises `SourceError` when the source cannot be read at
        all; a problem with one item is that item's, so `handle` deals with it.
        """
        ...

    def watch(self, handle: ItemHandler) -> Watcher | None:
        """Start handing new and changed items to `handle` as they appear.

        None for a kind that cannot be watched, which is synced instead.
        """
        ...
