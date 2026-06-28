"""
Prometheus metrics middleware.

Exposes /metrics endpoint with:
  - HTTP request count and latency (P50/P99)
  - LLM token consumption counter
  - Cache hit ratio gauge
  - Active request gauge

Usage (in main.py):
    from .middleware.prometheus_metrics import setup_prometheus
    setup_prometheus(app)
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

_registry_available = False
try:
    from prometheus_client import (  # noqa: PLC0415
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CollectorRegistry,
        REGISTRY,
    )
    _registry_available = True
except ImportError:
    pass


def setup_prometheus(app: FastAPI) -> None:
    """Register /metrics endpoint and add request-tracking middleware."""
    if not _registry_available:
        # No-op when prometheus_client is not installed
        @app.get("/metrics", include_in_schema=False)
        async def metrics_stub() -> PlainTextResponse:
            return PlainTextResponse("# prometheus_client not installed\n")
        return

    REQUEST_COUNT = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    REQUEST_LATENCY = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    ACTIVE_REQUESTS = Gauge(
        "http_active_requests",
        "Number of active HTTP requests",
    )

    LLM_TOKENS = Counter(
        "llm_tokens_total",
        "Total LLM tokens consumed",
        ["type"],  # prompt / completion / cache_read / cache_write
    )
    CACHE_HITS = Counter("semantic_cache_hits_total", "Semantic cache hits")
    CACHE_MISSES = Counter("semantic_cache_misses_total", "Semantic cache misses")

    # Expose counters so other modules can increment them
    app.state.prom_llm_tokens = LLM_TOKENS
    app.state.prom_cache_hits = CACHE_HITS
    app.state.prom_cache_misses = CACHE_MISSES

    @app.middleware("http")
    async def _track(request: Request, call_next: Callable) -> Response:
        endpoint = request.url.path
        method   = request.method
        ACTIVE_REQUESTS.inc()
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
            ACTIVE_REQUESTS.dec()
        return response

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(
            generate_latest(REGISTRY),
            media_type=CONTENT_TYPE_LATEST,
        )
