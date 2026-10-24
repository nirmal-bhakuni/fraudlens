"""A simple in-memory rate limiter (sliding window, one window per client).

Limits: it lives inside one process. It resets on restart and is not shared
between several app instances. For that you would use Redis. We skip it on purpose.
"""
import math
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException

from app.config import RATE_LIMIT_PER_MINUTE


class RateLimiter:
    def __init__(self, limit_per_minute: int, window_seconds: float = 60.0, clock=time.monotonic):
        self.limit = limit_per_minute
        self.window = window_seconds
        self.clock = clock
        self._hits: dict[str, deque] = defaultdict(deque)
        # FastAPI runs normal "def" endpoints in several threads, so we need a lock.
        self._lock = threading.Lock()

    def check(self, client_id: str) -> None:
        """Count this request, or raise 429 if the client is over the limit."""
        now = self.clock()
        with self._lock:
            hits = self._hits[client_id]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = max(1, math.ceil(self.window - (now - hits[0])))
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Limit is {self.limit} per minute.",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)