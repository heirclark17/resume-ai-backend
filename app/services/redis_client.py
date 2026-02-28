"""
Optional Redis connection manager.

Provides an async Redis client singleton that degrades gracefully
when REDIS_URL is not set or Redis is unreachable.
"""

import logging
from typing import Optional

_log = logging.getLogger(__name__)

_redis_client = None  # type: Optional["redis.asyncio.Redis"]


async def init_redis() -> None:
    """Connect to Redis if REDIS_URL is configured. Safe to call always."""
    global _redis_client
    from app.config import get_settings

    url = get_settings().redis_url
    if not url:
        _log.info("[redis] REDIS_URL not set — Redis features disabled")
        return

    try:
        import redis.asyncio as aioredis

        _redis_client = aioredis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        # Verify connectivity
        await _redis_client.ping()
        _log.info("[redis] Connected successfully")
    except Exception as exc:
        _log.warning(f"[redis] Connection failed ({exc}) — running without Redis")
        _redis_client = None


async def close_redis() -> None:
    """Gracefully close the Redis connection pool."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
            _log.info("[redis] Connection closed")
        except Exception:
            pass
        _redis_client = None


def get_redis():
    """Return the Redis client or None if unavailable."""
    return _redis_client


async def is_redis_healthy() -> bool:
    """Quick health probe — returns False rather than raising."""
    if _redis_client is None:
        return False
    try:
        return await _redis_client.ping()
    except Exception:
        return False
