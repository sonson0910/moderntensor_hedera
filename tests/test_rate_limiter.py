"""
Tests for sdk/rate_limiter.py — Token-bucket rate limiter
"""

import time
import pytest
from sdk.rate_limiter import RateLimiter


def test_acquire_within_capacity():
    limiter = RateLimiter(rate=100.0, capacity=10)
    # Should allow up to capacity
    for _ in range(10):
        assert limiter.acquire("miner-1") is True


def test_acquire_exceeds_capacity():
    limiter = RateLimiter(rate=0.1, capacity=2)  # Very slow refill
    assert limiter.acquire("miner-1") is True
    assert limiter.acquire("miner-1") is True
    assert limiter.acquire("miner-1") is False  # Exhausted


def test_separate_buckets_per_miner():
    limiter = RateLimiter(rate=0.1, capacity=1)
    assert limiter.acquire("miner-1") is True
    assert limiter.acquire("miner-2") is True  # Different bucket
    assert limiter.acquire("miner-1") is False  # miner-1 exhausted


def test_refill_over_time():
    limiter = RateLimiter(rate=100.0, capacity=2)  # 100 tokens/sec
    limiter.acquire("m1")
    limiter.acquire("m1")
    assert limiter.acquire("m1") is False

    time.sleep(0.05)  # Wait ~50ms → should refill ~5 tokens
    assert limiter.acquire("m1") is True


def test_get_stats():
    limiter = RateLimiter(rate=10.0, capacity=5)
    limiter.acquire("m1")
    stats = limiter.get_stats("m1")
    assert stats["miner_id"] == "m1"
    assert stats["capacity"] == 5.0
    assert stats["remaining_tokens"] <= 5.0


def test_get_all_stats():
    limiter = RateLimiter(rate=10.0, capacity=5)
    limiter.acquire("m1")
    limiter.acquire("m2")
    all_stats = limiter.get_all_stats()
    assert len(all_stats) == 2


def test_reset():
    limiter = RateLimiter(rate=0.1, capacity=1)
    limiter.acquire("m1")
    assert limiter.acquire("m1") is False

    limiter.reset("m1")
    assert limiter.acquire("m1") is True
