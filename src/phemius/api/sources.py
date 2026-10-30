from fastapi import APIRouter, Response, status

from phemius.api.pagination import DEFAULT_PAGE_SIZE, Limit, Offset, Page
from phemius.api.params import Id, OptionalQueryId
from phemius.services import sources
from phemius.services.sources import (
    NewSourceRequest,
    SourceChange,
    SourceExclusion,
    SourceView,
)
from phemius.store.sources import ActivityEntry, ExclusionOrder

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("")
def list_sources(
    limit: Limit = DEFAULT_PAGE_SIZE, offset: Offset = 0
) -> Page[SourceView]:
    """Sources in the order they were added."""
    items, total = sources.list_sources(limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("", status_code=status.HTTP_201_CREATED)
def add_source(request: NewSourceRequest) -> SourceView:
    """Add a source, then watch and sync it in the background."""
    source = sources.create_source(
        request.kind, request.config, request.name, request.rules
    )
    return sources.describe_source(source)


@router.get("/activity")
def list_activity(
    source_id: OptionalQueryId = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> Page[ActivityEntry]:
    """Recent activity, newest first, for every source or one."""
    page = sources.list_activity(source_id, limit, offset)
    return Page(items=page.items, total=page.total, limit=limit, offset=offset)


@router.get("/{source_id}")
def get_source(source_id: Id) -> SourceView:
    return sources.describe_source(sources.get_source(source_id))


@router.patch("/{source_id}")
def update_source(source_id: Id, change: SourceChange) -> SourceView:
    """Partial update. Rules merge: a rule sent as null follows the global
    setting again. A new config restarts the watcher and syncs."""
    return sources.describe_source(sources.update_source(source_id, change))


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: Id) -> Response:
    """Delete a source and its activity. Its documents stay in the library."""
    sources.delete_source(source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{source_id}/pause")
def pause_source(source_id: Id) -> SourceView:
    return sources.describe_source(sources.pause_source(source_id))


@router.post("/{source_id}/resume")
def resume_source(source_id: Id) -> SourceView:
    """Watch again and sync, which imports what changed while paused."""
    return sources.describe_source(sources.resume_source(source_id))


@router.post("/{source_id}/sync", status_code=status.HTTP_202_ACCEPTED)
def sync_source(source_id: Id) -> SourceView:
    """Sync now, in the background. A paused source is not synced."""
    return sources.describe_source(sources.request_sync(source_id))


@router.get("/{source_id}/exclusions")
def list_exclusions(
    source_id: Id,
    order_by: ExclusionOrder = "-created",
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> Page[SourceExclusion]:
    """Items whose document was deleted, so syncs do not import them again."""
    items, total = sources.list_exclusions(source_id, order_by, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.delete(
    "/{source_id}/exclusions/{exclusion_id}", status_code=status.HTTP_204_NO_CONTENT
)
def lift_exclusion(source_id: Id, exclusion_id: Id) -> Response:
    """Re-import an excluded item: an active source syncs now, a paused one on
    resume."""
    sources.lift_exclusion(source_id, exclusion_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
