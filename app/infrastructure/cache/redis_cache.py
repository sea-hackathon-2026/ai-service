"""
Redis cache adapter.

Provides a simple async Redis client wrapper for caching
job results, rate limiting data, and other temporary state.
Falls back gracefully when Redis is unavailable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Redis is optional — import conditionally
try:
    from redis.asyncio import Redis as AsyncRedis

    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    AsyncRedis = None  # type: ignore


class RedisCache:
    """Async Redis cache with graceful fallback."""

    def __init__(self, redis_url: str) -> None:
        self._url = redis_url
        self._client: Optional[AsyncRedis] = None  # type: ignore

    async def connect(self) -> None:
        """Initialize Redis connection."""
        if not _REDIS_AVAILABLE:
            logger.warning("Redis package not installed. Caching disabled.")
            return

        try:
            self._client = AsyncRedis.from_url(self._url, decode_responses=True)
            await self._client.ping()
            logger.info("Redis connected: %s", self._url)
        except Exception as e:
            logger.warning("Redis connection failed: %s. Caching disabled.", e)
            self._client = None

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Optional[str]:
        """Get a cached value by key."""
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception:
            return None

    async def set(
        self, key: str, value: Any, ttl_seconds: int = 3600
    ) -> bool:
        """Set a cached value with TTL."""
        if not self._client:
            return False
        try:
            serialized = json.dumps(value, default=str) if not isinstance(value, str) else value
            await self._client.set(key, serialized, ex=ttl_seconds)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """Delete a cached key."""
        if not self._client:
            return False
        try:
            result = await self._client.delete(key)
            return result > 0
        except Exception:
            return False

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._client is not None
