"""Bounded path and query parameters, so an out-of-range value is a 422, not a 500."""

from typing import Annotated

from fastapi import Path, Query

# SQLite's largest integer; a larger value would overflow in the store.
MAX_ID = 2**63 - 1

type Id = Annotated[int, Path(ge=1, le=MAX_ID)]
# A namespaced voice id such as `piper:en_US-joe-medium`; never a path.
type VoiceId = Annotated[
    str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
]
type OptionalQueryId = Annotated[int | None, Query(ge=1, le=MAX_ID)]
