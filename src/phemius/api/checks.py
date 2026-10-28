from fastapi import APIRouter

from phemius.services import checks
from phemius.services.checks import SetupCheckRun

router = APIRouter(prefix="/api/checks", tags=["checks"])


@router.get("")
def last_checks() -> SetupCheckRun | None:
    """The last run of the setup checks, or null before the first run."""
    return checks.last_run()


@router.post("")
def run_checks() -> SetupCheckRun:
    return checks.run_checks()
