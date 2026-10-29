"""Totals of the work done in a time window, for the Today panel."""

from dataclasses import dataclass

from phemius.store.database import transaction


@dataclass(frozen=True)
class WorkTotals:
    scripts_written: int
    # Sum over the scripts with a known cost; None when none had one.
    priced_cost_usd: float | None
    unpriced_scripts: int
    audio_files: int
    narration_seconds: float


def work_totals(start: float, end: float) -> WorkTotals:
    """Scripts written and audio finished from `start` (inclusive) to `end`."""
    with transaction() as connection:
        scripts = connection.execute(
            "SELECT COUNT(*) AS written, SUM(cost_usd) AS cost,"
            " COUNT(*) - COUNT(cost_usd) AS unpriced FROM jobs"
            " WHERE script_written >= ? AND script_written < ?",
            (start, end),
        ).fetchone()
        audio = connection.execute(
            "SELECT COUNT(*) AS files, TOTAL(a.duration_seconds) AS seconds"
            " FROM jobs j JOIN audio a ON a.id = j.audio_id"
            " WHERE j.state = 'done' AND j.finished >= ? AND j.finished < ?",
            (start, end),
        ).fetchone()
    return WorkTotals(
        scripts_written=scripts["written"],
        priced_cost_usd=scripts["cost"],
        unpriced_scripts=scripts["unpriced"],
        audio_files=audio["files"],
        narration_seconds=audio["seconds"],
    )
