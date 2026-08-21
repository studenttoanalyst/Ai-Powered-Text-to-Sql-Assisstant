"""Centralized logging configuration."""

from __future__ import annotations

import logging

from config.settings import settings


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a configured logger instance for reuse across modules."""
    logger_name = name or "text_to_sql_assistant"
    logger = logging.getLogger(logger_name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(handler)
    logger.propagate = False

    return logger
