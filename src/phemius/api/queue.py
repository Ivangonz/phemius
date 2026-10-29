from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from phemius.api.pagination import DEFAULT_PAGE_SIZE, Limit, Offset, Page
from phemius.api.params import Id
from phemius.services import queue
from phemius.store.jobs import Job, JobState

router = APIRouter(prefix="/api/queue", tags=["queue"])


class QueueStatus(BaseModel):
    is_paused: bool


class QueuePage(Page[Job]):
    is_paused: bool


@router.get("")
def list_jobs(
    state: Annotated[list[JobState] | None, Query()] = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Offset = 0,
) -> QueuePage:
    page = queue.list_jobs(state or [], limit, offset)
    return QueuePage(
        items=page.items,
        total=page.total,
        limit=limit,
        offset=offset,
        is_paused=queue.is_queue_paused(),
    )


@router.post("/pause")
def pause_queue() -> QueueStatus:
    queue.pause_queue()
    return QueueStatus(is_paused=True)


@router.post("/resume")
def resume_queue() -> QueueStatus:
    queue.resume_queue()
    return QueueStatus(is_paused=False)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: Id) -> Job:
    return queue.cancel_job(job_id)


@router.post("/{job_id}/retry")
def retry_job(job_id: Id) -> Job:
    return queue.retry_job(job_id)
