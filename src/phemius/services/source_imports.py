"""Import one item from a source under its import rules, and log what happened.

Every source kind goes through here, so the rules and the activity log behave
the same for a folder as for a repository.
"""

from pathlib import Path

import structlog

from phemius.config import load_config
from phemius.errors import PhemiusError
from phemius.services import maintenance, pipeline
from phemius.services.import_rules import EffectiveRules, ImportRules, effective_rules
from phemius.sources import SourceItem
from phemius.store import documents as document_store
from phemius.store import sources as source_store
from phemius.store.documents import StoredVersion
from phemius.store.sources import ActivityAction, NewActivity, StoredSource

log = structlog.get_logger(__name__)

DELETED_DETAIL = "Deleted from the library, so it is not imported again."


def import_item(source_id: int, item: SourceItem) -> None:
    """Import one item, unless its source was paused or deleted meanwhile."""
    source = source_store.get_source(source_id)
    if source is None or source["status"] != "active":
        return
    if source_store.is_excluded(source_id, item.key):
        source_store.record_activity(
            NewActivity(source_id, "skipped", item.name, DELETED_DETAIL)
        )
        return
    rules = rules_of(source)
    suffix = item.path.suffix.lower()
    if suffix not in rules.file_types:
        detail = f"{suffix} files are not imported from this source."
        source_store.record_activity(
            NewActivity(source_id, "skipped", item.name, detail)
        )
        return
    try:
        stored = pipeline.import_file(item.path, item.key, source_id)
    except Exception as error:  # one bad file must not stop the source
        log.warning(
            "source_item_failed",
            source_id=source_id,
            item=item.name,
            error_type=type(error).__name__,
        )
        source_store.record_activity(
            NewActivity(source_id, "failed", item.name, failure_text(error))
        )
        return
    if stored.outcome != "unchanged":
        _apply_rules(source_id, item, stored, rules)


def rules_of(source: StoredSource) -> EffectiveRules:
    return effective_rules(ImportRules.model_validate(source["rules"]), load_config())


def _apply_rules(
    source_id: int, item: SourceItem, stored: StoredVersion, rules: EffectiveRules
) -> None:
    if stored.outcome == "new_version" and not rules.keep_versions:
        _prune_earlier_versions(stored.document_id)
    action, detail = _queue_audio(stored, rules)
    source_store.record_activity(
        NewActivity(source_id, action, item.name, detail, stored.document_id)
    )


def _queue_audio(
    stored: StoredVersion, rules: EffectiveRules
) -> tuple[ActivityAction, str]:
    is_new = stored.outcome == "created"
    action: ActivityAction = "imported" if is_new else "updated"
    if is_new and not rules.auto_audio:
        return action, "Auto-generate is off for this source."
    if not is_new and not rules.regenerate_on_change:
        return action, "New version; its audio is not generated automatically."
    try:
        queued = pipeline.build_auto_audio(
            stored.document_id, rules.skip_not_recommended
        )
    except PhemiusError as error:  # the document is kept; only audio failed
        return "failed", pipeline.error_text(error)
    if queued is None:
        return "skipped", "Imported without audio: not recommended for listening."
    return action, "Audio queued."


def _prune_earlier_versions(document_id: int) -> None:
    # A backup or restore holding the gate must not lose files under it; the
    # next change to the document prunes what this one left.
    with maintenance.gate.worker_turn() as is_allowed:
        if not is_allowed:
            return
        paths = document_store.prune_earlier_versions(document_id)
        for recorded in paths:
            Path(recorded).unlink(missing_ok=True)
    log.info("earlier_versions_pruned", document_id=document_id, files=len(paths))


def failure_text(error: Exception) -> str:
    if isinstance(error, PhemiusError):
        return pipeline.error_text(error)
    return str(error) or type(error).__name__
