"""In-process fixed-window rate limiting with bounded memory."""

from __future__ import annotations

import asyncio
import time

from fastapi import Request

# Populated by middleware; cleared in tests via rate_limit.clear().
_buckets: dict[str, tuple[int, float]] = {}
_lock = asyncio.Lock()


def clear() -> None:
    _buckets.clear()


def client_ip(request: Request) -> str | None:
    """Resolve the client IP, honoring a single trusted X-Forwarded-For hop."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
        if candidate:
            return candidate
    if request.client and request.client.host:
        return request.client.host
    return None


def rate_limit_key(request: Request) -> str | None:
    """Key for throttling. Returns None when no stable client identity exists."""
    return client_ip(request)


async def is_rate_limited(key: str, limit: int, *, max_keys: int) -> bool:
    now = time.monotonic()
    async with _lock:
        _evict_expired(now)
        if len(_buckets) >= max_keys and key not in _buckets:
            # Under memory pressure, drop the oldest bucket rather than growing
            # without bound.
            oldest = min(_buckets, key=lambda k: _buckets[k][1])
            del _buckets[oldest]

        count, started = _buckets.get(key, (0, now))
        if now - started >= 60:
            count, started = 0, now
        count += 1
        _buckets[key] = (count, started)
        return count > limit


def _evict_expired(now: float) -> None:
    expired = [key for key, (_, started) in _buckets.items() if now - started >= 60]
    for key in expired:
        del _buckets[key]
