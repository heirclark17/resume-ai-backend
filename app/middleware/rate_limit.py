"""
Redis-backed sliding window rate limiter middleware.

Falls back to no-op when Redis is unavailable (slowapi decorators
on individual routes remain as backup).
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.services.redis_client import get_redis

_log = logging.getLogger(__name__)

# Requests per window
AUTHENTICATED_LIMIT = 200
ANONYMOUS_LIMIT = 60
WINDOW_SECONDS = 60

# Paths that bypass rate limiting
EXEMPT_PATHS = frozenset({"/health", "/health/ready", "/metrics", "/"})


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health/metrics endpoints
        if request.url.path in EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        r = get_redis()
        if r is None:
            # No Redis — fall through, slowapi decorators handle it
            return await call_next(request)

        # Determine identity and limit
        user_id = request.headers.get("x-user-id")
        if user_id:
            key = f"resumeai:rl:user:{user_id}"
            limit = AUTHENTICATED_LIMIT
        else:
            client_ip = request.client.host if request.client else "unknown"
            key = f"resumeai:rl:ip:{client_ip}"
            limit = ANONYMOUS_LIMIT

        try:
            pipe = r.pipeline(transaction=True)
            now = int(time.time())
            window_key = f"{key}:{now // WINDOW_SECONDS}"

            pipe.incr(window_key)
            pipe.expire(window_key, WINDOW_SECONDS + 1)
            results = await pipe.execute()

            current_count = results[0]
            remaining = max(0, limit - current_count)

            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(
                ((now // WINDOW_SECONDS) + 1) * WINDOW_SECONDS
            )

            if current_count > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again shortly."},
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(WINDOW_SECONDS),
                    },
                )

            return response

        except Exception as exc:
            _log.debug(f"[rate_limit] Redis error ({exc}) — skipping rate limit")
            return await call_next(request)
