"""Tests for app.core.rate_limiter.RateLimiter.

Uses very small periods so the blocking/sleep branch is exercised without
slowing down the test suite meaningfully.
"""

import time

from app.core.rate_limiter import RateLimiter


def test_allows_calls_up_to_max_without_blocking():
    limiter = RateLimiter(max_calls=3, period_seconds=60)

    start = time.monotonic()
    for _ in range(3):
        limiter.acquire()
    elapsed = time.monotonic() - start

    assert elapsed < 1.0


def test_blocks_until_window_frees_up():
    limiter = RateLimiter(max_calls=1, period_seconds=0.2)

    limiter.acquire()
    start = time.monotonic()
    limiter.acquire()
    elapsed = time.monotonic() - start

    assert elapsed >= 0.15


def test_old_calls_outside_window_are_forgotten():
    limiter = RateLimiter(max_calls=1, period_seconds=0.1)

    limiter.acquire()
    time.sleep(0.15)

    start = time.monotonic()
    limiter.acquire()
    elapsed = time.monotonic() - start

    assert elapsed < 0.1
