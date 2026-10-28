"""structlog setup. Log IDs and outcomes; never secrets or document text."""

import logging

import structlog

# SDK and HTTP client loggers whose debug and info records can carry request
# bodies (document text, scripts), full URLs or headers. Their warnings still show.
QUIET_LOGGERS = (
    "openai",
    "httpx2",
    "httpcore2",
    "httpx",
    "httpcore",
    "urllib3",
    "huggingface_hub",
)


class QuietThirdPartyFilter(logging.Filter):
    """Drops records below WARNING from `QUIET_LOGGERS`, whatever their level.

    Logger levels alone are not enough: the openai SDK sets its logger's level
    from `OPENAI_LOG` when it is imported, which may happen after we configure.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        is_quiet = record.name.partition(".")[0] in QUIET_LOGGERS
        return record.levelno >= logging.WARNING or not is_quiet


_QUIET_FILTER = QuietThirdPartyFilter()


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
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
