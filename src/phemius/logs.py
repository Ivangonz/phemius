"""structlog setup. Log IDs and outcomes; never secrets or document text."""

import logging

import structlog


def configure_logging(level: str) -> None:
    level_number = logging.getLevelNamesMapping().get(level, logging.INFO)
    logging.basicConfig(format="%(message)s", level=level_number)
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
import os
