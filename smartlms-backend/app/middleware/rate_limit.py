from collections import deque
from dataclasses import dataclass
from time import time
import asyncio

from fastapi import Request


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    reset_in_seconds: int


class InMemoryRateLimiter:
    """Simple sliding-window rate limiter keyed by client ip + request path."""

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max(1, max_requests)
        self.window_seconds = max(1, window_seconds)
        self._buckets: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> RateLimitResult:
        now = time()
        window_start = now - self.window_seconds

        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket

            while bucket and bucket[0] <= window_start:
                bucket.popleft()

            if len(bucket) >= self.max_requests:
                reset_in_seconds = max(1, int(self.window_seconds - (now - bucket[0])))
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_in_seconds=reset_in_seconds,
                )

            bucket.append(now)
            remaining = max(0, self.max_requests - len(bucket))

            # Opportunistic cleanup to avoid unbounded memory growth.
            if len(self._buckets) > 10000:
                stale_keys = [k for k, q in self._buckets.items() if not q or q[-1] <= window_start]
                for stale_key in stale_keys:
                    self._buckets.pop(stale_key, None)

            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_in_seconds=self.window_seconds,
            )

    async def snapshot(self) -> dict:
        """Return lightweight internal counters for health diagnostics."""
        now = time()
        window_start = now - self.window_seconds

        async with self._lock:
            active_keys = 0
            active_requests = 0
            for bucket in self._buckets.values():
                while bucket and bucket[0] <= window_start:
                    bucket.popleft()
                if bucket:
                    active_keys += 1
                    active_requests += len(bucket)

            return {
                "max_requests": self.max_requests,
                "window_seconds": self.window_seconds,
                "tracked_keys": len(self._buckets),
                "active_keys": active_keys,
                "active_requests_in_window": active_requests,
            }


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        # First IP is the original client in common reverse proxy setups.
        return forwarded_for.split(",")[0].strip()

    if request.client and request.client.host:
        return request.client.host

    return "unknown"


def key_for_request(request: Request) -> str:
    return f"{get_client_ip(request)}:{request.url.path}"