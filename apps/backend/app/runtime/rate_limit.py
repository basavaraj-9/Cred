from __future__ import annotations

import hashlib
import threading
import time
from typing import Protocol

from app.core.config import Settings
from app.core.exceptions import AppError


class RateLimitStore(Protocol):
    def increment(self, key: str, window: int) -> int: ...


class MemoryRateLimitStore:
    def __init__(self) -> None:
        self.entries: dict[str, tuple[int, float]] = {}
        self.lock = threading.Lock()

    def increment(self, key: str, window: int) -> int:
        with self.lock:
            now = time.monotonic()
            if len(self.entries) > 10000:
                self.entries = {k: v for k, v in self.entries.items() if v[1] > now}
            count, expires = self.entries.get(key, (0, now + window))
            if expires <= now:
                count, expires = 0, now + window
            self.entries[key] = count + 1, expires
            return count + 1


class RedisRateLimitStore:
    def __init__(self, url: str):
        from redis import Redis

        self.client = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)

    def increment(self, key: str, window: int) -> int:
        result = self.client.eval(
            "local n=redis.call('INCR',KEYS[1]); "
            "if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
            1,
            key,
            window,
        )
        return int(result)


def build_store(settings: Settings) -> RateLimitStore:
    return (
        RedisRateLimitStore(settings.redis_url or "")
        if settings.rate_limit_backend == "redis"
        else MemoryRateLimitStore()
    )


def check_rate(settings: Settings, store: RateLimitStore, identity: str, category: str) -> None:
    limit = (
        settings.login_rate_limit_per_minute
        if category == "login"
        else settings.expensive_rate_limit_per_minute
        if category == "expensive"
        else settings.rate_limit_per_minute
    )
    key = "cip:rate:" + hashlib.sha256(f"{category}:{identity}".encode()).hexdigest()
    try:
        count = store.increment(key, 60)
    except Exception as exc:
        raise AppError("DEPENDENCY_UNAVAILABLE", "Rate limit service unavailable", 503) from exc
    if count > limit:
        raise AppError("RATE_LIMITED", "Request limit exceeded; try again later", 429)
