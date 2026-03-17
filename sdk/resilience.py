"""
Resilience Patterns — Retry with Backoff + Circuit Breaker

Provides fault-tolerance for miner calls in the orchestrator:

- RetryWithBackoff: Retry failed calls with exponential backoff + jitter
- CircuitBreaker:   Prevent repeated calls to failing miners (CLOSED→OPEN→HALF_OPEN)
"""

import time
import random
import logging
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class RetryExhaustedError(Exception):
    """All retry attempts exhausted."""

    def __init__(self, last_error: Exception, attempts: int):
        self.last_error = last_error
        self.attempts = attempts
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_error}")


class CircuitOpenError(Exception):
    """Circuit breaker is OPEN — calls are rejected."""

    def __init__(self, miner_id: str = "", recovery_at: float = 0.0):
        self.miner_id = miner_id
        self.recovery_at = recovery_at
        remaining = max(0, recovery_at - time.time())
        super().__init__(
            f"Circuit OPEN for {miner_id}. "
            f"Recovery in {remaining:.1f}s"
        )


# ──────────────────────────────────────────────────────────────
# Retry with Exponential Backoff
# ──────────────────────────────────────────────────────────────


class RetryWithBackoff:
    """
    Retry a callable with exponential backoff and jitter.

    Usage:
        retry = RetryWithBackoff(max_retries=3, base_delay=1.0)
        result = retry.execute(some_function, arg1, arg2)
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

        # Stats
        self.total_attempts = 0
        self.total_successes = 0
        self.total_failures = 0

    def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute func with retries. Raises RetryExhaustedError on failure."""
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            self.total_attempts += 1
            try:
                result = func(*args, **kwargs)
                self.total_successes += 1
                if attempt > 1:
                    logger.info("Retry succeeded on attempt %d", attempt)
                return result
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self._calc_delay(attempt)
                    logger.warning(
                        "Attempt %d/%d failed: %s — retrying in %.2fs",
                        attempt,
                        self.max_retries,
                        e,
                        delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "Attempt %d/%d failed: %s — no more retries",
                        attempt,
                        self.max_retries,
                        e,
                    )

        self.total_failures += 1
        raise RetryExhaustedError(last_error, self.max_retries)  # type: ignore[arg-type]

    def _calc_delay(self, attempt: int) -> float:
        delay = min(
            self.base_delay * (self.backoff_factor ** (attempt - 1)),
            self.max_delay,
        )
        if self.jitter:
            delay *= random.uniform(0.5, 1.5)
        return delay

    def get_stats(self) -> dict:
        return {
            "total_attempts": self.total_attempts,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
        }


# ──────────────────────────────────────────────────────────────
# Circuit Breaker
# ──────────────────────────────────────────────────────────────


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Circuit breaker prevents cascading failures.

    State machine:
        CLOSED  --[failure_threshold reached]--> OPEN
        OPEN    --[recovery_timeout elapsed]---> HALF_OPEN
        HALF_OPEN --[success]---> CLOSED
        HALF_OPEN --[failure]---> OPEN
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 3,
        name: str = "",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self.name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float = 0.0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        # Auto-transition OPEN → HALF_OPEN if recovery timeout elapsed
        if self._state == CircuitState.OPEN:
            if time.time() - self._opened_at >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info("Circuit %s: OPEN → HALF_OPEN", self.name)
        return self._state

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute func through the circuit breaker."""
        current = self.state

        if current == CircuitState.OPEN:
            raise CircuitOpenError(self.name, self._opened_at + self.recovery_timeout)

        if current == CircuitState.HALF_OPEN and self._half_open_calls >= self.half_open_max:
            self._trip()
            raise CircuitOpenError(self.name, self._opened_at + self.recovery_timeout)

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_calls = 0
            logger.info("Circuit %s: HALF_OPEN → CLOSED", self.name)
        self._success_count += 1

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._trip()
        elif self._failure_count >= self.failure_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.time()
        self._half_open_calls = 0
        logger.warning("Circuit %s: → OPEN (failures=%d)", self.name, self._failure_count)

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0

    def get_state(self) -> str:
        return self.state.value

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
