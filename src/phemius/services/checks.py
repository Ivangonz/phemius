"""Setup checks: what a self-hoster still has to fix, for S7 and the C3 summary.

Checks run in parallel, each with a short timeout, so a provider that is down
cannot hold up the rest. The last run is kept in memory only: it describes this
process's environment (installed tools, reachable providers), which a restart
can change, so after a restart there is no last run until the checks run again.
"""

import shutil
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import structlog
from pydantic import BaseModel

from phemius.config import OFFLINE_PROVIDER, load_config
from phemius.errors import PhemiusError
from phemius.models import get_script_model
from phemius.services import sources
from phemius.services.ffmpeg import check_ffmpeg
from phemius.services.health import is_writable
from phemius.services.script_models import active_model
from phemius.services.voices import check_engine
from phemius.voices import kokoro

log = structlog.get_logger(__name__)

type CheckStatus = Literal["ok", "optional", "needs_attention"]
type CheckId = Literal[
    "python", "script_model", "voice_engine", "library", "watch_folder", "ffmpeg"
]

CHECK_TIMEOUT_SECONDS = 3.0
GIGABYTE = 1024**3
MIN_FREE_BYTES = GIGABYTE


class SetupCheck(BaseModel):
    id: CheckId
    label: str
    detail: str
    status: CheckStatus
    hint: str | None = None


class CheckSummary(BaseModel):
    ok: int
    optional: int
    needs_attention: int


class SetupCheckRun(BaseModel):
    checks: list[SetupCheck]
    summary: CheckSummary
    ran_at: datetime


@dataclass(frozen=True)
class Outcome:
    status: CheckStatus
    detail: str
    hint: str | None = None


@dataclass(frozen=True)
class TimedOutcome:
    outcome: Outcome
    duration_ms: int


@dataclass(frozen=True)
class Check:
    id: CheckId
    label: str
    run: Callable[[], Outcome]


_last_run: SetupCheckRun | None = None


def running_python() -> tuple[int, int]:
    return sys.version_info.major, sys.version_info.minor


def last_run() -> SetupCheckRun | None:
    return _last_run


def run_checks() -> SetupCheckRun:
    """Run every check in parallel; one that does not answer in time needs attention."""
    global _last_run
    futures = [_start(check) for check in CHECKS]
    wait(futures, timeout=CHECK_TIMEOUT_SECONDS)
    results = [
        _collect(check, future) for check, future in zip(CHECKS, futures, strict=True)
    ]
    summary = _summarize(results)
    _last_run = SetupCheckRun(checks=results, summary=summary, ran_at=datetime.now(UTC))
    log.info("setup_checks_ran", **summary.model_dump())
    return _last_run


def _start(check: Check) -> Future[TimedOutcome]:
    future: Future[TimedOutcome] = Future()

    def run() -> None:
        started = time.perf_counter()
        outcome = _run_safely(check)
        duration_ms = round((time.perf_counter() - started) * 1000)
        future.set_result(TimedOutcome(outcome, duration_ms))

    # A daemon thread rather than an executor: a check that never answers must
    # not keep the response, or the process at shutdown, waiting for it.
    threading.Thread(target=run, name=f"setup-check-{check.id}", daemon=True).start()
    return future


def _run_safely(check: Check) -> Outcome:
    try:
        return check.run()
    except PhemiusError as error:
        return Outcome("needs_attention", error.message, error.hint)
    except Exception as error:
        # The message is left out: it may echo a URL or a provider reply.
        log.exception("setup_check_failed", check_id=check.id)
        return Outcome(
            "needs_attention",
            f"The check failed with {type(error).__name__}.",
            "See the Phemius logs for details.",
        )


def _collect(check: Check, future: Future[TimedOutcome]) -> SetupCheck:
    if not future.done():
        log.warning(
            "setup_check_timed_out",
            check_id=check.id,
            timeout_seconds=CHECK_TIMEOUT_SECONDS,
        )
        outcome = Outcome(
            "needs_attention",
            f"The check did not answer within {CHECK_TIMEOUT_SECONDS:g} s.",
            "Check that the service is running and reachable, then run again.",
        )
    else:
        timed = future.result()
        outcome = timed.outcome
        log.info(
            "setup_check",
            check_id=check.id,
            status=outcome.status,
            duration_ms=timed.duration_ms,
        )
    return SetupCheck(
        id=check.id,
        label=check.label,
        detail=outcome.detail,
        status=outcome.status,
        hint=outcome.hint,
    )


def _summarize(results: list[SetupCheck]) -> CheckSummary:
    counts = Counter(result.status for result in results)
    return CheckSummary(
        ok=counts["ok"],
        optional=counts["optional"],
        needs_attention=counts["needs_attention"],
    )


def _python() -> Outcome:
    version = running_python()
    low, high = kokoro.SUPPORTED_PYTHON
    supported = f"{low[0]}.{low[1]} to {high[0]}.{high[1]}"
    name = f"Python {version[0]}.{version[1]}"
    if low <= version <= high:
        return Outcome("ok", f"{name} is in Kokoro's range ({supported}).")
    # Only Kokoro is limited to these versions; other engines run anywhere.
    is_kokoro = load_config().voice_engine == kokoro.ENGINE_NAME
    return Outcome(
        "needs_attention" if is_kokoro else "optional",
        f"{name} is outside Kokoro's range ({supported}).",
        f"Run Phemius on Python {high[0]}.{high[1]} to use Kokoro voices.",
    )


def _script_model() -> Outcome:
    active = active_model()
    if active.error is not None:
        return Outcome("needs_attention", active.error, active.hint)
    if active.provider == OFFLINE_PROVIDER:
        return Outcome(
            "optional",
            "Offline rules write scripts; no script model is set up.",
            "Choose a script model in Settings for natural-sounding scripts.",
        )
    result = get_script_model(load_config()).check()
    name = f"{result.model} ({active.provider})"
    if not result.is_reachable:
        return Outcome("needs_attention", f"{name}: {result.error}", result.hint)
    latency = "" if result.latency_ms is None else f" in {result.latency_ms:.0f} ms"
    return Outcome("ok", f"{name} answered{latency}.")


def _voice_engine() -> Outcome:
    result = check_engine()
    status: CheckStatus = "ok" if result.is_ready else "needs_attention"
    return Outcome(status, result.message, result.hint)


def _library() -> Outcome:
    data_dir = load_config().data_dir
    if not is_writable(data_dir):
        return Outcome(
            "needs_attention",
            f"{data_dir} is not writable.",
            f"Make {data_dir} writable or set PHEMIUS_DATA_DIR.",
        )
    free_bytes = shutil.disk_usage(data_dir).free
    detail = f"{free_bytes / GIGABYTE:.1f} GB free in {data_dir}."
    if free_bytes < MIN_FREE_BYTES:
        return Outcome("needs_attention", detail, "Free up space for new audio.")
    return Outcome("ok", detail)


def _watch_folder() -> Outcome:
    active = sources.active_sources()
    if not active:
        return Outcome(
            "optional",
            "No sources are set.",
            "Add a folder source or set PHEMIUS_WATCH_DIR to add documents"
            " automatically.",
        )
    for source in active:
        problem = sources.find_problem(source)
        if problem is not None:
            return Outcome(
                "needs_attention", f"{source['name']}: {problem.message}", problem.hint
            )
    count = len(active)
    return Outcome("ok", f"{count} source{'s are' if count > 1 else ' is'} readable.")


def _ffmpeg() -> Outcome:
    result = check_ffmpeg()
    output_format = load_config().output_format
    # Missing ffmpeg is fine for WAV, but with M4A or MP3 configured every audio
    # falls back to WAV, so it needs attention.
    if result.status == "optional" and output_format != "wav":
        detail = f"{result.message} The output format is {output_format.upper()}."
        return Outcome("needs_attention", detail, result.hint)
    return Outcome(result.status, result.message, result.hint)


CHECKS: tuple[Check, ...] = (
    Check("python", "Python version", _python),
    Check("script_model", "Script model", _script_model),
    Check("voice_engine", "Voice engine", _voice_engine),
    Check("library", "Library folder", _library),
    Check("watch_folder", "Watched folder", _watch_folder),
    Check("ffmpeg", "ffmpeg", _ffmpeg),
)
