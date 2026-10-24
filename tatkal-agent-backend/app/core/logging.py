"""
Structured application logging setup.

Configures a consistent log format with contextual fields.
Sensitive data (passwords, API keys, tokens) must never be logged.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """Produces human-readable, structured log lines for development."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        base = (
            f"{timestamp} | {record.levelname:<8} | "
            f"{record.name} | {record.getMessage()}"
        )
        if record.exc_info and record.exc_info[0] is not None:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging(level: str = "INFO") -> None:
    """
    Configure root logger with structured output to stderr.

    Args:
        level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(StructuredFormatter())

    root = logging.getLogger()
    # Remove any pre-existing handlers to prevent duplicate output
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    # Quieten noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if level.upper() == "DEBUG" else logging.WARNING
    )
