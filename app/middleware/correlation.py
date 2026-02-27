"""
Correlation ID middleware for request tracing.

Generates a UUID4 correlation ID per request (or accepts X-Correlation-ID from client).
Stores in contextvars for propagation to logs and downstream services.
"""
import uuid
import time
import contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.utils.logger import logger

# Context variable for correlation ID - accessible from any async code in the request
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")
request_user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_user_id", default="")


def get_correlation_id() -> str:
    """Get the current request's correlation ID"""
    return correlation_id_var.get("")


def get_request_user_id() -> str:
    """Get the current request's user ID"""
    return request_user_id_var.get("")


class CorrelationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Generates or accepts X-Correlation-ID
    2. Stores it in contextvars for log propagation
    3. Logs structured request/response info with timing
    4. Returns correlation ID in response headers
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Accept from client or generate new
        cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        correlation_id_var.set(cid)

        # Extract user ID from headers for log context
        user_id = request.headers.get("x-user-id", "")
        request_user_id_var.set(user_id)

        start = time.monotonic()
        method = request.method
        path = request.url.path

        # Log request start
        logger.info(
            "request.started",
            extra={
                "correlation_id": cid,
                "method": method,
                "path": path,
                "user_id": user_id,
                "client_ip": request.client.host if request.client else "",
            }
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.monotonic() - start) * 1000)
            logger.error(
                "request.failed",
                extra={
                    "correlation_id": cid,
                    "method": method,
                    "path": path,
                    "user_id": user_id,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            )
            raise

        duration_ms = round((time.monotonic() - start) * 1000)
        status = response.status_code

        # Log request completion
        log_fn = logger.warning if status >= 400 else logger.info
        log_fn(
            "request.completed",
            extra={
                "correlation_id": cid,
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": duration_ms,
                "user_id": user_id,
            }
        )

        # Return correlation ID in response headers
        response.headers["X-Correlation-ID"] = cid
        return response
