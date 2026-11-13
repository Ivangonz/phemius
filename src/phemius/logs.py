"""structlog setup. Log IDs and outcomes; never secrets or document text."""

import logging

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
REDACTED_MESSAGE = "third_party_log_redacted error_type=%s"


class QuietThirdPartyFilter(logging.Filter):
    """Drops records below WARNING from `QUIET_LOGGERS`, whatever their level.

    Logger levels alone are not enough: the openai SDK sets its logger's level
    from `OPENAI_LOG` when it is imported, which may happen after we configure.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        is_quiet = record.name.partition(".")[0] in QUIET_LOGGERS
        return record.levelno >= logging.WARNING or not is_quiet


class RedactThirdPartyFilter(logging.Filter):
    """Keeps only the level, logger name and error type of `REDACTED_LOGGERS`."""

    def filter(self, record: logging.LogRecord) -> bool:
        is_redactable = record.name.partition(".")[0] in REDACTED_LOGGERS
        # Every root handler runs this filter on the same record; redact once.
        if is_redactable and record.msg is not REDACTED_MESSAGE:
            _redact(record)
        return True


def _redact(record: logging.LogRecord) -> None:
    error_type = record.exc_info[0] if record.exc_info else None
    record.msg = REDACTED_MESSAGE
    record.args = (error_type.__name__ if error_type else "none",)
    record.exc_info = None
    record.exc_text = None
    record.stack_info = None


_QUIET_FILTER = QuietThirdPartyFilter()
_REDACT_FILTER = RedactThirdPartyFilter()


def configure_logging(level: str) -> None:
    level_number = logging.getLevelNamesMapping().get(level, logging.INFO)
    logging.basicConfig(format="%(message)s", level=level_number)
    _quiet_third_party_loggers(level_number)
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
