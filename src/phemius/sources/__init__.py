"""Source kinds. Adding one means adding one module with a `from_config` factory
and one line to `SOURCE_KINDS`.
"""

from collections.abc import Callable, Mapping

from phemius.errors import InvalidInputError
from phemius.sources import folder
from phemius.sources.base import ItemHandler, Source, SourceItem, Watcher

__all__ = [
    "SOURCE_KINDS",
    "ItemHandler",
    "Source",
    "SourceItem",
    "Watcher",
    "get_source",
]

# Validates a source's config (raising `InvalidInputError`) and builds the source.
type SourceFactory = Callable[[Mapping[str, object]], Source]

SOURCE_KINDS: dict[str, SourceFactory] = {
    "folder": folder.from_config,
}


def get_source(kind: str, config: Mapping[str, object]) -> Source:
    factory = SOURCE_KINDS.get(kind)
    if factory is None:
        raise InvalidInputError(
            f"Unknown source kind '{kind}'.",
            hint=f"Use one of: {', '.join(SOURCE_KINDS)}.",
            field="kind",
        )
    return factory(config)
