"""structlog setup. Log IDs and outcomes; never secrets or document text."""

import logging
from collections.abc import Callable
from typing import Any

import structlog

# SDK, HTTP client and voice engine loggers whose debug and info records can
# carry request bodies (document text, scripts), full URLs or headers. Their
# warnings still show.
QUIET_LOGGERS = (
    "openai",
    "httpx2",
    "httpcore2",
    "httpx",
    "httpcore",
    "urllib3",
    "huggingface_hub",
    "piper",
)
# Piper's phonemizers put the sentence being spoken in warnings and errors
# (`Failed to phonemize sentence: %s`, with a traceback that may repeat it).
REDACTED_LOGGERS = ("piper",)
REDACTED_MESSAGE = "third_party_log_redacted logger=%s level=%s error_type=%s"
REDACTED_MARKER = "is_redacted"


class QuietThirdPartyFilter(logging.Filter):
    """Drops records below WARNING from `QUIET_LOGGERS`, whatever their level.

    Logger levels alone are not enough: the openai SDK sets its logger's level
    from `OPENAI_LOG` when it is imported, which may happen after we configure.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        is_quiet = record.name.partition(".")[0] in QUIET_LOGGERS
        return record.levelno >= logging.WARNING or not is_quiet


class RedactingRecordFactory:
    """Redacts `REDACTED_LOGGERS` records as they are created.

    Redacting at creation means no handler sees the original text, wherever it
    is attached or however handlers are ordered.
    """

    def __init__(self, previous: Callable[..., logging.LogRecord]) -> None:
        self._previous = previous

    def __call__(self, *args: Any, **kwargs: Any) -> logging.LogRecord:
        record = self._previous(*args, **kwargs)
        _redact_if_needed(record)
        return record


class RedactThirdPartyFilter(logging.Filter):
    """Backstop for a record factory installed after ours that drops it."""

    def filter(self, record: logging.LogRecord) -> bool:
        _redact_if_needed(record)
        return True


def _redact_if_needed(record: logging.LogRecord) -> None:
    is_redactable = record.name.partition(".")[0] in REDACTED_LOGGERS
    if is_redactable and not getattr(record, REDACTED_MARKER, False):
        _redact(record)


def _redact(record: logging.LogRecord) -> None:
    error_type = record.exc_info[0] if record.exc_info else None
    # The production format is `%(message)s`, so the message itself must
    # carry the logger name and level.
    record.msg = REDACTED_MESSAGE
    record.args = (
        record.name,
        record.levelname,
        error_type.__name__ if error_type else "none",
    )
    record.exc_info = None
    record.exc_text = None
    record.stack_info = None
    setattr(record, REDACTED_MARKER, True)


def _install_redacting_record_factory() -> None:
    current = logging.getLogRecordFactory()
    if not isinstance(current, RedactingRecordFactory):
        logging.setLogRecordFactory(RedactingRecordFactory(current))


_QUIET_FILTER = QuietThirdPartyFilter()
_REDACT_FILTER = RedactThirdPartyFilter()


def configure_logging(level: str) -> None:
    level_number = logging.getLevelNamesMapping().get(level, logging.INFO)
    logging.basicConfig(format="%(message)s", level=level_number)
    _quiet_third_party_loggers(level_number)
    _install_redacting_record_factory()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_number),
        # Uncached so structlog.testing.capture_logs works in tests.
        cache_logger_on_first_use=False,
    )


def _quiet_third_party_loggers(level_number: int) -> None:
    root = logging.getLogger()
    # basicConfig is a no-op when OPENAI_LOG made the SDK install a handler first.
    root.setLevel(level_number)
    for handler in root.handlers:
        handler.addFilter(_QUIET_FILTER)
        handler.addFilter(_REDACT_FILTER)
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
