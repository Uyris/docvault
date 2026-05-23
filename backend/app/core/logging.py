"""Structured logging.

Every query flows through here as a single JSON line carrying latency, token
counts, estimated cost, cache hit/miss and eval scores. Those same fields are
also persisted to Postgres (see ``QueryLog``) to feed the /metrics dashboard —
the log line is for humans tailing stdout, the table is for aggregation.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import settings

_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    # Human-friendly console output in dev, machine-readable JSON elsewhere.
    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer()
        if settings.app_env == "development"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str = "docvault") -> structlog.stdlib.BoundLogger:
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)
