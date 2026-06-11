"""Logging configuration for the trading bot.

Sets up dual-handler logging:
  - File handler  : detailed JSON-style records in logs/trading_bot.log
  - Console handler: concise human-readable output
"""

import logging
import os
from datetime import datetime, timezone


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "trading_bot.log")


class _JsonStyleFormatter(logging.Formatter):
    """Produces structured, easy-to-parse log lines for the file handler."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        return (
            f'{{"timestamp": "{timestamp}", '
            f'"level": "{record.levelname}", '
            f'"module": "{record.module}", '
            f'"message": "{record.getMessage()}"}}'
        )


class _ConsoleFormatter(logging.Formatter):
    """Concise colourless format for terminal output."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        return f"[{timestamp}] {record.levelname:<8} {record.getMessage()}"


def setup_logging() -> logging.Logger:
    """Initialise and return the root application logger.

    Call once at application startup (CLI entry point).
    Subsequent modules should use ``logging.getLogger(__name__)``.
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("trading_bot")
    # Avoid adding duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # --- File handler (DEBUG level -- captures everything) ---
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_JsonStyleFormatter())

    # --- Console handler (INFO level -- user-facing) ---
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(_ConsoleFormatter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
