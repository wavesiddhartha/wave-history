from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    def __init__(self, *, max_requests: int, window_seconds: int = 60):
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(1, int(window_seconds))
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def consume(self, key: str) -> RateLimitResult:
        now = monotonic()
        with self._lock:
            queue = self._hits.get(key)
            if queue is None:
                queue = deque()
                self._hits[key] = queue

            cutoff = now - self.window_seconds
            while queue and queue[0] <= cutoff:
                queue.popleft()

            if len(queue) >= self.max_requests:
                retry_after = int(max(1, self.window_seconds - (now - queue[0])))
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            queue.append(now)
            remaining = max(0, self.max_requests - len(queue))

            # Opportunistic cleanup to prevent stale key growth.
            if len(self._hits) > 4096:
                stale_keys = [entry for entry, values in self._hits.items() if not values or values[-1] <= cutoff]
                for stale in stale_keys[:1024]:
                    self._hits.pop(stale, None)

            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                retry_after_seconds=0,
            )
