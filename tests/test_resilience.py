"""
Tests for sdk/resilience.py — RetryWithBackoff + CircuitBreaker
"""

import pytest
from sdk.resilience import (
    RetryWithBackoff,
    RetryExhaustedError,
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


# ──────────────────────────────────────────────────────────────
# RetryWithBackoff Tests
# ──────────────────────────────────────────────────────────────


def test_retry_succeeds_first_try():
    retry = RetryWithBackoff(max_retries=3, base_delay=0.01)
    result = retry.execute(lambda: 42)
    assert result == 42
    assert retry.total_successes == 1


def test_retry_succeeds_after_failures():
    call_count = 0

    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("not yet")
        return "ok"

    retry = RetryWithBackoff(max_retries=3, base_delay=0.01)
    result = retry.execute(flaky)
    assert result == "ok"
    assert call_count == 3


def test_retry_exhausted():
    retry = RetryWithBackoff(max_retries=2, base_delay=0.01)
    with pytest.raises(RetryExhaustedError) as exc_info:
        retry.execute(lambda: 1 / 0)
    assert exc_info.value.attempts == 2
    assert retry.total_failures == 1


def test_retry_stats():
    retry = RetryWithBackoff(max_retries=1, base_delay=0.01)
    retry.execute(lambda: 1)
    stats = retry.get_stats()
    assert stats["total_attempts"] == 1
    assert stats["total_successes"] == 1


# ──────────────────────────────────────────────────────────────
# CircuitBreaker Tests
# ──────────────────────────────────────────────────────────────


def test_circuit_starts_closed():
    cb = CircuitBreaker(failure_threshold=3, name="test")
    assert cb.state == CircuitState.CLOSED


def test_circuit_opens_on_threshold():
    def failing():
        raise RuntimeError("fail")

    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=100, name="test")

    for _ in range(2):
        try:
            cb.call(failing)
        except RuntimeError:
            pass

    assert cb.state == CircuitState.OPEN


def test_circuit_rejects_when_open():
    def failing():
        raise RuntimeError("fail")

    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=100, name="test")
    try:
        cb.call(failing)
    except RuntimeError:
        pass

    assert cb.state == CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        cb.call(lambda: "should not reach")


def test_circuit_reset():
    def failing():
        raise RuntimeError("fail")

    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=100, name="test")
    try:
        cb.call(failing)
    except RuntimeError:
        pass
    assert cb.state == CircuitState.OPEN

    cb.reset()
    assert cb.state == CircuitState.CLOSED


def test_circuit_stats():
    cb = CircuitBreaker(failure_threshold=5, name="test")
    cb.call(lambda: True)
    stats = cb.get_stats()
    assert stats["state"] == "CLOSED"
    assert stats["success_count"] == 1
