"""
Lightweight in-process metrics — exposes counters and histograms for
AI call duration, errors, queue depth, and circuit breaker states.

These metrics are emitted as structured JSON logs (consumed by Railway log drain)
and optionally exposed via /metrics for Prometheus scraping.
"""

import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Dict, Any

from app.utils.logger import get_logger

logger = get_logger()

# ---------------------------------------------------------------------------
# In-process counters
# ---------------------------------------------------------------------------

_counters: Dict[str, int] = defaultdict(int)
_histograms: Dict[str, list] = defaultdict(list)

MAX_HISTOGRAM_SAMPLES = 500  # Rolling window


def inc(name: str, value: int = 1) -> None:
    """Increment a counter."""
    _counters[name] += value


def observe(name: str, value: float) -> None:
    """Record a histogram observation (e.g., duration)."""
    bucket = _histograms[name]
    bucket.append(value)
    if len(bucket) > MAX_HISTOGRAM_SAMPLES:
        _histograms[name] = bucket[-MAX_HISTOGRAM_SAMPLES:]


@asynccontextmanager
async def track_duration(service: str, operation: str = "call"):
    """
    Context manager that tracks call duration and success/failure.

    Usage:
        async with track_duration("openai", "tailor"):
            result = await openai_call(...)
    """
    start = time.monotonic()
    try:
        yield
        duration = time.monotonic() - start
        observe(f"{service}.{operation}.duration_ms", duration * 1000)
        inc(f"{service}.{operation}.success")
        logger.info(
            "metrics.call",
            extra={
                "service": service,
                "operation": operation,
                "duration_ms": round(duration * 1000, 1),
                "status": "success",
            },
        )
    except Exception:
        duration = time.monotonic() - start
        observe(f"{service}.{operation}.duration_ms", duration * 1000)
        inc(f"{service}.{operation}.error")
        logger.warning(
            "metrics.call",
            extra={
                "service": service,
                "operation": operation,
                "duration_ms": round(duration * 1000, 1),
                "status": "error",
            },
        )
        raise


def get_snapshot() -> Dict[str, Any]:
    """Return a snapshot of all counters and histogram summaries."""
    snapshot: Dict[str, Any] = {"counters": dict(_counters)}

    summaries = {}
    for name, samples in _histograms.items():
        if samples:
            sorted_s = sorted(samples)
            p50_idx = int(len(sorted_s) * 0.5)
            p95_idx = int(len(sorted_s) * 0.95)
            p99_idx = int(len(sorted_s) * 0.99)
            summaries[name] = {
                "count": len(sorted_s),
                "p50": round(sorted_s[p50_idx], 1),
                "p95": round(sorted_s[min(p95_idx, len(sorted_s) - 1)], 1),
                "p99": round(sorted_s[min(p99_idx, len(sorted_s) - 1)], 1),
                "max": round(sorted_s[-1], 1),
            }
    snapshot["histograms"] = summaries
    return snapshot


def reset() -> None:
    """Reset all metrics (useful for testing)."""
    _counters.clear()
    _histograms.clear()
