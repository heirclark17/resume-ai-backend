"""
L1 Redis cache layer.

All operations are fire-and-forget safe — a Redis failure never
becomes an HTTP error. Returns None on miss or error.
"""

import json
import logging
from typing import Any, Optional

from app.services.redis_client import get_redis

_log = logging.getLogger(__name__)

KEY_PREFIX = "resumeai:"


async def cache_get(key: str) -> Optional[Any]:
    """Fetch a JSON-serialized value from Redis. Returns None on miss or error."""
    r = get_redis()
    if r is None:
        return None
    try:
        raw = await r.get(f"{KEY_PREFIX}{key}")
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        _log.debug(f"[cache] GET {key} failed: {exc}")
        return None


async def cache_set(key: str, value: Any, ttl: int = 3600) -> bool:
    """Store a JSON-serializable value in Redis with TTL (seconds). Returns success."""
    r = get_redis()
    if r is None:
        return False
    try:
        await r.set(f"{KEY_PREFIX}{key}", json.dumps(value), ex=ttl)
        return True
    except Exception as exc:
        _log.debug(f"[cache] SET {key} failed: {exc}")
        return False


async def cache_delete(key: str) -> bool:
    """Remove a key from Redis. Returns success."""
    r = get_redis()
    if r is None:
        return False
    try:
        await r.delete(f"{KEY_PREFIX}{key}")
        return True
    except Exception as exc:
        _log.debug(f"[cache] DEL {key} failed: {exc}")
        return False
