"""
Token-Bucket Rate Limiter per Miner

Prevents any single miner from being called too frequently.
Each miner gets its own bucket that refills at a configurable rate.

Usage:
    from sdk.rate_limiter import RateLimiter

    limiter = RateLimiter(rate=10.0, capacity=20)

    if limiter.acquire("0.0.1001"):
        # proceed with miner call
    else:
        # rate limited — skip or queue
"""

import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _Bucket:
    """Internal token bucket state."""
    tokens: float
    capacity: float
    rate: float  # tokens per second
    last_refill: float = field(default_factory=time.time)

    def refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    def consume(self) -> bool:
        self.refill()
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    """
    Per-miner token-bucket rate limiter.

    Args:
        rate:     Tokens added per second (e.g., 10.0 = 10 calls/sec)
        capacity: Maximum burst size (bucket capacity)
    """

    def __init__(self, rate: float = 10.0, capacity: int = 20):
        self.rate = rate
        self.capacity = capacity
        self._buckets: dict[str, _Bucket] = {}

    def _get_bucket(self, miner_id: str) -> _Bucket:
        if miner_id not in self._buckets:
            self._buckets[miner_id] = _Bucket(
                tokens=float(self.capacity),
                capacity=float(self.capacity),
                rate=self.rate,
            )
        return self._buckets[miner_id]

    def acquire(self, miner_id: str) -> bool:
        """
        Try to acquire a token for the given miner.

        Returns True if allowed, False if rate limited.
        """
        bucket = self._get_bucket(miner_id)
        allowed = bucket.consume()
        if not allowed:
            logger.warning("Rate limited: miner %s", miner_id)
        return allowed

    def get_stats(self, miner_id: str) -> dict:
        """Get rate limiter stats for a miner."""
        bucket = self._get_bucket(miner_id)
        bucket.refill()
        return {
            "miner_id": miner_id,
            "remaining_tokens": round(bucket.tokens, 2),
            "capacity": bucket.capacity,
            "rate": bucket.rate,
        }

    def get_all_stats(self) -> list[dict]:
        """Get stats for all tracked miners."""
        return [self.get_stats(mid) for mid in self._buckets]

    def reset(self, miner_id: str) -> None:
        """Reset a miner's bucket to full capacity."""
        if miner_id in self._buckets:
            self._buckets[miner_id].tokens = float(self.capacity)
            self._buckets[miner_id].last_refill = time.time()
