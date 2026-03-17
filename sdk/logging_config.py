"""
Structured Logging for ModernTensor

Provides JSON-formatted structured logging with:
- Timestamps, log level, module, message
- Correlation ID support (via contextvars) for tracing task flows
- Easy setup: call setup_logging() once at startup

Usage:
    from sdk.logging_config import setup_logging, get_logger, set_correlation_id

    setup_logging(level="INFO", json_format=True)
    logger = get_logger("my_module")
    set_correlation_id("task-12345")
    logger.info("Processing task", extra={"miner_id": "0.0.1001"})
"""

import os
import sys
import json
import logging
import contextvars
from datetime import datetime, timezone

# ──────────────────────────────────────────────────────────────
# Correlation ID (thread-safe via contextvars)
# ──────────────────────────────────────────────────────────────

_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def set_correlation_id(cid: str) -> None:
    """Set the correlation ID for the current async/thread context."""
    _correlation_id.set(cid)


def get_correlation_id() -> str:
    """Get the current correlation ID."""
    return _correlation_id.get()


# ──────────────────────────────────────────────────────────────
# JSON Formatter
# ──────────────────────────────────────────────────────────────


class JsonFormatter(logging.Formatter):
    """Outputs log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Inject correlation_id if set
        cid = _correlation_id.get()
        if cid:
            log_entry["correlation_id"] = cid

        # Include any extra fields
        for key in ("miner_id", "task_id", "subnet_id", "duration_ms", "error"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        # Include exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


# ──────────────────────────────────────────────────────────────
# Readable Formatter (for development)
# ──────────────────────────────────────────────────────────────


class ReadableFormatter(logging.Formatter):
    """Human-friendly log format for development."""

    FORMAT = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    DATEFMT = "%H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self.FORMAT, datefmt=self.DATEFMT)

    def format(self, record: logging.LogRecord) -> str:
        cid = _correlation_id.get()
        if cid:
            record.msg = f"[{cid}] {record.msg}"
        return super().format(record)


# ──────────────────────────────────────────────────────────────
# Setup
# ──────────────────────────────────────────────────────────────

_is_configured = False


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    log_file: str = "",
) -> None:
    """
    Configure structured logging for the entire application.

    Args:
        level:       Log level string (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON formatter (True) or readable (False)
        log_file:    Path to log file. Empty = stdout only.
    """
    global _is_configured
    if _is_configured:
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers
    root.handlers.clear()

    formatter: logging.Formatter
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = ReadableFormatter()

    # Stdout handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # File handler (optional)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        root.addHandler(fh)

    # Suppress noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    _is_configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Call setup_logging() first for structured output."""
    return logging.getLogger(name)
