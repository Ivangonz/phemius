"""Today's totals for S4: scripts, audio files, narration minutes and cost.

"Today" is the calendar day at the caller's UTC offset (UTC by default). The
server's own time zone is not used: in Docker it is usually UTC, which is
rarely the listener's day. An offset is enough, so no time zone database is
needed.
"""

from datetime import UTC, date, datetime, timedelta, timezone

from pydantic import BaseModel

from phemius.store import stats as stats_store

SECONDS_PER_MINUTE = 60


class TodayStats(BaseModel):
    date: date
    utc_offset_minutes: int
    scripts_written: int
    audio_files: int
    narration_minutes: float
    # Covers the scripts with a known cost; `unpriced_scripts` counts the rest.
    # Null when scripts were written today and none had a known cost.
    estimated_cost_usd: float | None
    unpriced_scripts: int


def today_stats(utc_offset_minutes: int = 0) -> TodayStats:
    day_start = _day_start(datetime.now(UTC), utc_offset_minutes)
    day_end = day_start + timedelta(days=1)
    totals = stats_store.work_totals(day_start.timestamp(), day_end.timestamp())
    has_no_scripts = totals.scripts_written == 0
    return TodayStats(
        date=day_start.date(),
        utc_offset_minutes=utc_offset_minutes,
        scripts_written=totals.scripts_written,
        audio_files=totals.audio_files,
        narration_minutes=totals.narration_seconds / SECONDS_PER_MINUTE,
        estimated_cost_usd=0.0 if has_no_scripts else totals.priced_cost_usd,
        unpriced_scripts=totals.unpriced_scripts,
    )


def _day_start(now: datetime, utc_offset_minutes: int) -> datetime:
    local_now = now.astimezone(timezone(timedelta(minutes=utc_offset_minutes)))
    return local_now.replace(hour=0, minute=0, second=0, microsecond=0)
