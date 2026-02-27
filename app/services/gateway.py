"""
External Service Gateway — circuit breaker, concurrency limiter, retry, timeout.

Wraps all calls to OpenAI, Perplexity, Firecrawl, Playwright with:
  1. Circuit breaker (fail-fast when provider is down)
  2. Concurrency semaphore (prevent overload)
  3. Timeout enforcement
  4. Retry with exponential backoff + jitter

Usage:
    gw = get_gateway()
    result = await gw.execute("openai", my_async_callable, arg1, kwarg=val)
"""
import asyncio
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Optional

from app.utils.logger import logger
from app.utils.metrics import inc, observe


# ---------------------------------------------------------------------------
# Configuration per external service
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ServiceConfig:
    max_concurrent: int = 10
    timeout_seconds: float = 90.0
    max_retries: int = 2
    circuit_failure_threshold: int = 5
    circuit_recovery_seconds: float = 30.0
    base_backoff_seconds: float = 1.0


GATEWAY_CONFIG: Dict[str, ServiceConfig] = {
    "openai": ServiceConfig(
        max_concurrent=10,
        timeout_seconds=90.0,
        max_retries=2,
        circuit_failure_threshold=5,
        circuit_recovery_seconds=30.0,
    ),
    "perplexity": ServiceConfig(
        max_concurrent=5,
        timeout_seconds=30.0,
        max_retries=2,
        circuit_failure_threshold=3,
        circuit_recovery_seconds=30.0,
    ),
    "firecrawl": ServiceConfig(
        max_concurrent=3,
        timeout_seconds=45.0,
        max_retries=1,
        circuit_failure_threshold=3,
        circuit_recovery_seconds=60.0,
    ),
    "playwright": ServiceConfig(
        max_concurrent=2,
        timeout_seconds=60.0,
        max_retries=1,
        circuit_failure_threshold=2,
        circuit_recovery_seconds=60.0,
    ),
}


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-service circuit breaker (thread-safe via asyncio single-thread model)."""

    def __init__(self, service: str, config: ServiceConfig):
        self.service = service
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self.success_count_half_open = 0

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            elapsed = time.monotonic() - self.last_failure_time
            if elapsed >= self.config.circuit_recovery_seconds:
                self.state = CircuitState.HALF_OPEN
                self.success_count_half_open = 0
                logger.info(
                    "circuit.half_open",
                    extra={"service": self.service, "after_seconds": round(elapsed, 1)},
                )
                return True
            return False
        # HALF_OPEN — allow one probe request at a time
        return True

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.success_count_half_open += 1
            if self.success_count_half_open >= 2:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("circuit.closed", extra={"service": self.service})
        else:
            self.failure_count = 0

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(
                "circuit.open",
                extra={"service": self.service, "reason": "half_open probe failed"},
            )
        elif self.failure_count >= self.config.circuit_failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                "circuit.open",
                extra={
                    "service": self.service,
                    "failures": self.failure_count,
                    "threshold": self.config.circuit_failure_threshold,
                },
            )


# ---------------------------------------------------------------------------
# Retryable error detection
# ---------------------------------------------------------------------------

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable(exc: Exception) -> bool:
    """Return True if the error is transient and worth retrying."""
    # OpenAI / httpx style
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status and int(status) in _RETRYABLE_STATUS_CODES:
        return True
    # Connection / timeout errors
    if isinstance(exc, (asyncio.TimeoutError, ConnectionError, OSError)):
        return True
    name = type(exc).__name__.lower()
    if any(kw in name for kw in ("timeout", "connection", "rate")):
        return True
    return False


# ---------------------------------------------------------------------------
# Gateway (singleton)
# ---------------------------------------------------------------------------

class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open and the request is rejected."""

    def __init__(self, service: str):
        self.service = service
        super().__init__(f"Circuit breaker OPEN for {service} — request rejected")


class ServiceGateway:
    """Central gateway for all external service calls."""

    def __init__(self) -> None:
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._semaphores: Dict[str, asyncio.Semaphore] = {}

        for service, cfg in GATEWAY_CONFIG.items():
            self._circuits[service] = CircuitBreaker(service, cfg)
            self._semaphores[service] = asyncio.Semaphore(cfg.max_concurrent)

    async def execute(
        self,
        service: str,
        fn: Callable[..., Coroutine],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute an async callable through the gateway.

        Applies: circuit breaker → semaphore → timeout → retry.
        """
        cfg = GATEWAY_CONFIG.get(service)
        if not cfg:
            # Unknown service — pass through without protection
            return await fn(*args, **kwargs)

        cb = self._circuits[service]
        sem = self._semaphores[service]

        if not cb.allow_request():
            raise CircuitOpenError(service)

        last_exc: Optional[Exception] = None
        start = time.monotonic()
        for attempt in range(1 + cfg.max_retries):
            try:
                async with sem:
                    result = await asyncio.wait_for(
                        fn(*args, **kwargs),
                        timeout=cfg.timeout_seconds,
                    )
                duration_ms = (time.monotonic() - start) * 1000
                cb.record_success()
                inc(f"{service}.success")
                observe(f"{service}.duration_ms", duration_ms)
                return result

            except Exception as exc:
                last_exc = exc
                cb.record_failure()
                inc(f"{service}.error")

                if attempt < cfg.max_retries and _is_retryable(exc):
                    backoff = cfg.base_backoff_seconds * (2 ** attempt)
                    jitter = random.uniform(0, backoff * 0.5)
                    wait = backoff + jitter
                    logger.warning(
                        "gateway.retry",
                        extra={
                            "service": service,
                            "attempt": attempt + 1,
                            "error": str(exc)[:200],
                            "wait_seconds": round(wait, 2),
                        },
                    )
                    await asyncio.sleep(wait)
                    # Re-check circuit before retry
                    if not cb.allow_request():
                        raise CircuitOpenError(service) from exc
                else:
                    logger.error(
                        "gateway.failed",
                        extra={
                            "service": service,
                            "attempt": attempt + 1,
                            "error": str(exc)[:200],
                        },
                    )
                    raise

        # Should not reach here, but just in case
        raise last_exc  # type: ignore[misc]

    def get_circuit_states(self) -> Dict[str, str]:
        """Return current circuit breaker states (for health check)."""
        return {svc: cb.state.value for svc, cb in self._circuits.items()}


# Singleton
_gateway: Optional[ServiceGateway] = None


def get_gateway() -> ServiceGateway:
    global _gateway
    if _gateway is None:
        _gateway = ServiceGateway()
    return _gateway
