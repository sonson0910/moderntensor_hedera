"""
Tests for new SDK modules: resilience, rate_limiter, metrics, logging_config, schemas.

Covers:
- CircuitBreaker: state transitions, call-through, open/half-open recovery
- RetryWithBackoff: retry success on transient failure
- RateLimiter: token bucket consume / reject
- MetricsCollector: class-based Prometheus metrics
- Structured logging: setup_logging, correlation IDs
- Pydantic schemas: validation, serialization
"""

import pytest
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk.resilience import CircuitBreaker, RetryWithBackoff, CircuitOpenError, CircuitState, RetryExhaustedError
from sdk.rate_limiter import RateLimiter
from sdk.logging_config import setup_logging, set_correlation_id, get_correlation_id
from sdk.protocol.schemas import TaskInput, MinerOutput


# =====================================================================
# CircuitBreaker Tests
# =====================================================================

class TestCircuitBreaker:
    def test_closed_passes_through(self):
        """Calls pass through when circuit is CLOSED."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1, name="test_closed")
        result = cb.call(lambda: 42)
        assert result == 42
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_threshold(self):
        """Circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1, name="test_open")

        for _ in range(2):
            try:
                cb.call(lambda: (_ for _ in ()).throw(ValueError("boom")))
            except ValueError:
                pass

        assert cb.state == CircuitState.OPEN

    def test_open_rejects_calls(self):
        """Open circuit raises CircuitOpenError."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60, name="test_reject")

        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        except ValueError:
            pass

        with pytest.raises(CircuitOpenError):
            cb.call(lambda: "should not reach")

    def test_half_open_recovery(self):
        """Circuit enters HALF_OPEN after timeout, recovers on success."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1, name="test_half")

        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        except ValueError:
            pass

        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Next call should go through (HALF_OPEN)
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_reset(self):
        """Manual reset clears failure count and closes circuit."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60, name="test_reset")

        try:
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))
        except ValueError:
            pass

        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


# =====================================================================
# RetryWithBackoff Tests
# =====================================================================

class TestRetryWithBackoff:
    def test_succeeds_first_try(self):
        """Should return immediately on success."""
        r = RetryWithBackoff(max_retries=3, base_delay=0.01)
        result = r.execute(lambda: "ok")
        assert result == "ok"

    def test_retries_then_succeeds(self):
        """Should retry on failure and succeed eventually."""
        r = RetryWithBackoff(max_retries=3, base_delay=0.01)
        attempts = {"count": 0}

        def flaky():
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise ValueError("not yet")
            return "finally"

        result = r.execute(flaky)
        assert result == "finally"
        assert attempts["count"] == 3

    def test_exhausts_retries(self):
        """Should raise after exhausting retries."""
        r = RetryWithBackoff(max_retries=2, base_delay=0.01)

        with pytest.raises(RetryExhaustedError):
            r.execute(lambda: (_ for _ in ()).throw(ValueError("always fail")))


# =====================================================================
# RateLimiter Tests
# =====================================================================

class TestRateLimiter:
    def test_allows_within_limit(self):
        """Should allow calls within the token budget."""
        rl = RateLimiter(rate=10.0, capacity=5)
        for _ in range(5):
            assert rl.acquire("client_a") is True

    def test_rejects_over_limit(self):
        """Should reject when tokens exhausted."""
        rl = RateLimiter(rate=0.0, capacity=2)  # rate=0 means no refill
        assert rl.acquire("client_b") is True
        assert rl.acquire("client_b") is True
        assert rl.acquire("client_b") is False

    def test_separate_clients(self):
        """Different client keys should have separate buckets."""
        rl = RateLimiter(rate=0.0, capacity=1)
        assert rl.acquire("x") is True
        assert rl.acquire("x") is False
        assert rl.acquire("y") is True  # different bucket


# =====================================================================
# Metrics Tests (class-based MetricsCollector)
# =====================================================================

class TestMetrics:
    def test_collector_instantiation(self):
        """MetricsCollector should instantiate without error."""
        # Import directly to avoid circular import from sdk.__init__
        from sdk.metrics import MetricsCollector
        mc = MetricsCollector(namespace="test_new_mod")
        assert mc is not None

    def test_record_task_created(self):
        """Recording task creation should not raise."""
        from sdk.metrics import MetricsCollector
        mc = MetricsCollector(namespace="test_rec_task")
        mc.record_task_created(subnet_id=1)

    def test_record_miner_call(self):
        """Recording miner call should not raise."""
        from sdk.metrics import MetricsCollector
        mc = MetricsCollector(namespace="test_rec_miner")
        mc.record_miner_call("miner_001", success=True, duration_ms=150.5)
        mc.record_miner_call("miner_001", success=False, duration_ms=5000)


# =====================================================================
# Logging Tests
# =====================================================================

class TestStructuredLogging:
    def test_setup_returns_none(self):
        """setup_logging configures module and returns None."""
        result = setup_logging()
        assert result is None  # setup_logging returns None

    def test_logger_works_after_setup(self):
        """After setup_logging, standard loggers should work."""
        import logging
        setup_logging()
        log = logging.getLogger("test.module")
        assert log is not None
        assert hasattr(log, "info")
        assert hasattr(log, "error")

    def test_correlation_id(self):
        """Correlation ID should be set and retrieved per-thread."""
        set_correlation_id("abc123")
        assert get_correlation_id() == "abc123"

        set_correlation_id("xyz789")
        assert get_correlation_id() == "xyz789"


# =====================================================================
# Pydantic Schema Tests
# =====================================================================

class TestSchemas:
    def test_task_input_valid(self):
        """Valid TaskInput should parse correctly."""
        data = {
            "task_type": "code_review",
            "payload": {"code": "print('hi')"},
            "subnet_id": 1,
        }
        ti = TaskInput(**data)
        assert ti.subnet_id == 1
        assert ti.task_type == "code_review"
        assert ti.payload == {"code": "print('hi')"}

    def test_task_input_invalid_type(self):
        """Invalid task_type should be rejected."""
        with pytest.raises(Exception):  # ValidationError
            TaskInput(
                task_type="nonexistent_type",
                payload={},
                subnet_id=0,
            )

    def test_miner_output_valid(self):
        """Valid MinerOutput should parse correctly."""
        mo = MinerOutput(
            analysis="Looks good",
            findings=[{"issue": "none"}],
            score=0.9,
            confidence=0.85,
        )
        assert mo.analysis == "Looks good"
        assert mo.score == 0.9
        assert mo.confidence == 0.85

    def test_task_input_serialization(self):
        """Schema should serialize to dict cleanly."""
        ti = TaskInput(
            task_type="code_review",
            payload={"code": "x = 1"},
            subnet_id=2,
        )
        d = ti.model_dump()
        assert isinstance(d, dict)
        assert d["subnet_id"] == 2
        assert d["task_type"] == "code_review"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
