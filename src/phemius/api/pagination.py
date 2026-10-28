"""Shared paging for list endpoints: `?limit=` (default 25, max 100) and `?offset=`."""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100

type Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
type Offset = Annotated[int, Query(ge=0)]


class Page[Item](BaseModel):
    items: list[Item]
    total: int
    limit: int
    offset: int
