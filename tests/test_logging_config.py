"""
Tests for sdk/logging_config.py — Structured JSON logging + correlation ID
"""

import json
import logging
from sdk.logging_config import (
    setup_logging,
    get_logger,
    set_correlation_id,
    get_correlation_id,
    JsonFormatter,
    ReadableFormatter,
)


def test_json_formatter_basic():
    """JsonFormatter produces valid JSON."""
    fmt = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="hello world",
        args=None,
        exc_info=None,
    )
    output = fmt.format(record)
    data = json.loads(output)
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert "timestamp" in data


def test_json_formatter_with_correlation_id():
    """JsonFormatter includes correlation_id when set."""
    set_correlation_id("task-abc-123")
    fmt = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="t.py",
        lineno=1, msg="test msg", args=None, exc_info=None,
    )
    output = fmt.format(record)
    data = json.loads(output)
    assert data["correlation_id"] == "task-abc-123"
    set_correlation_id("")  # cleanup


def test_correlation_id_get_set():
    set_correlation_id("cid-999")
    assert get_correlation_id() == "cid-999"
    set_correlation_id("")


def test_readable_formatter():
    fmt = ReadableFormatter()
    record = logging.LogRecord(
        name="test", level=logging.WARNING, pathname="t.py",
        lineno=5, msg="warn message", args=None, exc_info=None,
    )
    output = fmt.format(record)
    assert "warn message" in output
    assert "WARNING" in output


def test_get_logger():
    logger = get_logger("my_module")
    assert logger.name == "my_module"
