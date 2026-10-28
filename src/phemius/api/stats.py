from typing import Annotated

from fastapi import APIRouter, Query

from phemius.services import stats
from phemius.services.stats import TodayStats

router = APIRouter(prefix="/api/stats", tags=["stats"])

# Real-world offsets run from UTC-12:00 to UTC+14:00.
type UtcOffsetMinutes = Annotated[int, Query(ge=-12 * 60, le=14 * 60)]


@router.get("/today")
def today(utc_offset_minutes: UtcOffsetMinutes = 0) -> TodayStats:
    """Work done today: the calendar day at `utc_offset_minutes` (default UTC).

    Browsers can send `-new Date().getTimezoneOffset()`.
    """
    return stats.today_stats(utc_offset_minutes)
