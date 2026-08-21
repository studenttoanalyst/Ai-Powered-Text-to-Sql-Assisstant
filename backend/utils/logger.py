"""Centralized logging configuration."""

from __future__ import annotations

import logging


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a configured logger instance."""
    logger_name = name or "fmcg_chatbot"
    logger = logging.getLogger(logger_name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        logger.addHandler(handler)
        logger.propagate = False

    return logger
