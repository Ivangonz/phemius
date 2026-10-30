"""Bounded integer parameters, so an out-of-range value is a 422 and not a 500."""

from typing import Annotated

from fastapi import Path, Query

# SQLite's largest integer; a larger value would overflow in the store.
MAX_ID = 2**63 - 1

type Id = Annotated[int, Path(ge=1, le=MAX_ID)]
type OptionalQueryId = Annotated[int | None, Query(ge=1, le=MAX_ID)]
