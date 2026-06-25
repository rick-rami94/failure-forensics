"""Observability — structured logging that never records sensitive content.

Logs carry only safe metadata (trace ids, step names, counts, latency). Prompts, model
outputs, and document text are deliberately never logged — that content lives only in the
redacted trace store. This keeps logs safe to ship to any aggregator.
"""

from __future__ import annotations

import logging
import os

_LOGGER_NAME = "forensics"
_configured = False


def configure_logging(level: str | None = None) -> logging.Logger:
    """Configure and return the package logger. Idempotent."""
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    resolved = (level or os.environ.get("FORENSICS_LOG_LEVEL", "INFO")).upper()
    logger.setLevel(resolved)
    if not _configured:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(handler)
        logger.propagate = False
        _configured = True
    return logger


def get_logger() -> logging.Logger:
    """Return the package logger (configuring it on first use)."""
    return configure_logging()
