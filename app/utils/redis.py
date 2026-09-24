"""Redis client (async).

Used for availability cache (Slice 2) and outbox queue (Slice 7).
"""

from __future__ import annotations

import redis.asyncio as redis

from app.config.settings import settings

_client: redis.Redis | None = None


async def init_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_redis() -> redis.Redis:
    if _client is None:
        raise RuntimeError("Redis is not initialised. Call init_redis() on startup.")
    return _client
