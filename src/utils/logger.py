# src/utils/logger.py
"""Structured logging configuration for the ETL pipeline."""

import logging
import sys
import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for structured, readable pipeline logs.

    Args:
        log_level: Python logging level name (DEBUG, INFO, WARNING, ERROR).
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    """Return a bound structlog logger.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.
    """
    return structlog.get_logger(name)
