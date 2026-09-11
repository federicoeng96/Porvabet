import threading
import time
from collections import deque


class RateLimiter:
    """Simple blocking rate limiter: at most `max_calls` calls in any rolling
    `period_seconds` window. Used to respect a source's stated request budget
    (e.g. fbref's documented 10 requests/minute) from a single process.

    Not distributed — if you run multiple ingestion workers against the same
    source, each needs its own budget headroom or a shared external limiter.
    """

    def __init__(self, max_calls: int, period_seconds: float) -> None:
        self._max_calls = max_calls
        self._period_seconds = period_seconds
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            while self._calls and now - self._calls[0] > self._period_seconds:
                self._calls.popleft()
            if len(self._calls) >= self._max_calls:
                sleep_for = self._period_seconds - (now - self._calls[0])
                if sleep_for > 0:
                    time.sleep(sleep_for)
                now = time.monotonic()
                while self._calls and now - self._calls[0] > self._period_seconds:
                    self._calls.popleft()
            self._calls.append(time.monotonic())
