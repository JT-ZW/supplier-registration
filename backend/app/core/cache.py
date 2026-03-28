"""
Lightweight response cache with optional Redis backend.

Behavior:
- If REDIS_URL is configured and redis package is available, values are stored in Redis.
- Otherwise falls back to in-process memory cache.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import time
from typing import Any, Optional

from .config import settings
from .logger import logger

Redis = None
try:
    redis_asyncio = importlib.import_module("redis.asyncio")
    Redis = getattr(redis_asyncio, "Redis", None)
except Exception:  # pragma: no cover - optional dependency
    Redis = None


class ResponseCache:
    """Simple async cache wrapper for JSON-serializable payloads."""

    def __init__(self) -> None:
        self._memory: dict[str, tuple[float, str]] = {}
        self._lock = asyncio.Lock()
        self._redis: Optional[Any] = None
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._invalidations = 0

        if settings.REDIS_URL and Redis is not None:
            try:
                self._redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
                logger.info("Response cache configured with Redis backend")
            except Exception as exc:
                logger.warning("Redis cache initialization failed, using memory cache: %s", exc)

    async def get_json(self, key: str) -> Optional[dict[str, Any]]:
        """Get cached JSON payload by key."""
        if self._redis is not None:
            try:
                value = await self._redis.get(key)
                if value:
                    self._hits += 1
                    return json.loads(value)
                self._misses += 1
                return None
            except Exception as exc:
                logger.warning("Redis cache get failed for key %s: %s", key, exc)

        async with self._lock:
            cached = self._memory.get(key)
            if not cached:
                self._misses += 1
                return None
            expires_at, payload = cached
            if expires_at <= time.time():
                self._memory.pop(key, None)
                self._misses += 1
                return None
            self._hits += 1
            return json.loads(payload)

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        """Store JSON payload with TTL."""
        serialized = json.dumps(value, default=str)

        if self._redis is not None:
            try:
                await self._redis.set(key, serialized, ex=ttl_seconds)
                self._sets += 1
                return
            except Exception as exc:
                logger.warning("Redis cache set failed for key %s: %s", key, exc)

        async with self._lock:
            self._memory[key] = (time.time() + ttl_seconds, serialized)
            self._sets += 1

    async def delete(self, key: str) -> bool:
        """Delete a single key from cache."""
        removed = False
        if self._redis is not None:
            try:
                removed = (await self._redis.delete(key)) > 0
            except Exception as exc:
                logger.warning("Redis cache delete failed for key %s: %s", key, exc)

        async with self._lock:
            if key in self._memory:
                self._memory.pop(key, None)
                removed = True

        if removed:
            self._invalidations += 1
        return removed

    async def delete_prefix(self, prefix: str) -> int:
        """Delete all keys matching a prefix."""
        removed_count = 0

        if self._redis is not None:
            try:
                async for key in self._redis.scan_iter(match=f"{prefix}*"):
                    removed_count += await self._redis.delete(key)
            except Exception as exc:
                logger.warning("Redis cache delete_prefix failed for prefix %s: %s", prefix, exc)

        async with self._lock:
            keys = [k for k in self._memory.keys() if k.startswith(prefix)]
            for key in keys:
                self._memory.pop(key, None)
            removed_count += len(keys)

        if removed_count > 0:
            self._invalidations += removed_count
        return removed_count

    async def get_stats(self) -> dict[str, Any]:
        """Return lightweight cache diagnostics."""
        async with self._lock:
            memory_entries = len(self._memory)

        return {
            "backend": "redis" if self._redis is not None else "memory",
            "hits": self._hits,
            "misses": self._misses,
            "sets": self._sets,
            "invalidations": self._invalidations,
            "memory_entries": memory_entries,
        }


_cache_instance: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    """Get singleton cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ResponseCache()
    return _cache_instance
