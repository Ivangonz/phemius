"""Import rules: what a source does with the documents it brings in.

A source saves only the rules it overrides; the rest follow the global settings
(`skip_not_recommended`, `watch_on_change`) or the defaults below, so changing a
global setting still reaches every source that never chose otherwise.
"""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from phemius.config import Config
from phemius.services import ingest


def _file_types(values: list[str]) -> list[str]:
    normalized = {"." + value.strip().lower().lstrip(".") for value in values}
    unsupported = sorted(normalized - ingest.SUPPORTED)
    if unsupported:
        supported = ", ".join(sorted(ingest.SUPPORTED))
        raise ValueError(f"Unsupported: {', '.join(unsupported)}. Use {supported}.")
    return sorted(normalized)


type FileTypes = Annotated[list[str], Field(min_length=1), AfterValidator(_file_types)]


class ImportRules(BaseModel):
    """A source's own rules. None follows the global setting."""

    model_config = ConfigDict(extra="forbid")

    auto_audio: bool | None = Field(
        default=None, description="Generate audio for new documents."
    )
    skip_not_recommended: bool | None = Field(
        default=None,
        description="Import documents rated not_recommended without audio.",
    )
    keep_versions: bool | None = Field(
        default=None,
        description="Keep earlier versions and their audio when a document changes.",
    )
    regenerate_on_change: bool | None = Field(
        default=None, description="Generate audio for each new version."
    )
    file_types: FileTypes | None = Field(
        default=None, description="Extensions to import, such as .md."
    )


class EffectiveRules(BaseModel):
    """The rules a source applies, with the global settings filled in."""

    auto_audio: bool
    skip_not_recommended: bool
    keep_versions: bool
    regenerate_on_change: bool
    file_types: list[str]


def effective_rules(rules: ImportRules, config: Config) -> EffectiveRules:
    defaults = EffectiveRules(
        auto_audio=True,
        skip_not_recommended=config.skip_not_recommended,
        keep_versions=True,
        regenerate_on_change=config.watch_on_change == "regenerate",
        file_types=sorted(ingest.SUPPORTED),
    )
    return defaults.model_copy(update=rules.model_dump(exclude_none=True))


def merge_rules(saved: ImportRules, change: ImportRules) -> ImportRules:
    """Apply the rules sent in `change`; a rule sent as null follows the global
    setting again."""
    sent = change.model_dump(include=change.model_fields_set)
    return ImportRules.model_validate({**saved.model_dump(exclude_none=True), **sent})
