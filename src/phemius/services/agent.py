"""Categorizes documents and writes their spoken scripts with the configured model.

With no model configured the offline rules do both. A configured model that fails a
script raises `ModelError` so the audio fails with a hint; it never falls back to an
offline script. A failed analysis falls back to the rules, and the error is kept in
`last_error` so the UI can show it.
"""

import structlog

from phemius.config import load_config
from phemius.errors import ModelError
from phemius.models import get_script_model
from phemius.models.base import Analysis, Script
from phemius.models.offline import OfflineModel
from phemius.models.spoken_text import to_spoken_text

log = structlog.get_logger(__name__)

# Most recent analysis failure, shown in the UI so a bad key or model is not silent.
last_error: str | None = None


def analyze(title: str, text: str) -> Analysis:
    try:
        return get_script_model(load_config()).analyze(title, text)
    except (ModelError, ValueError) as error:  # analysis may fall back (#23)
        _record_analysis_failure(error)
    return OfflineModel().analyze(title, text)


def make_script(title: str, text: str, tone: str) -> Script:
    """Write a spoken script. Raises `ModelError` if the configured model fails.

    Every model gets the same speakable input: code marked, tables flattened, URLs
    and images removed.
    """
    model = get_script_model(load_config())
    return model.write_script(title, to_spoken_text(text), tone)


def _record_analysis_failure(error: ModelError | ValueError) -> None:
    global last_error
    last_error = error.message if isinstance(error, ModelError) else str(error)
    log.warning("analysis_fell_back", error_type=type(error).__name__)
