from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request

log = logging.getLogger("api")


async def request_logging_middleware(request: Request, call_next):
    req_id = uuid.uuid4().hex[:8]
    start = time.time()
    query = f"?{request.url.query}" if request.url.query else ""
    log.info("[%s] >>> %s %s%s", req_id, request.method, request.url.path, query)

    try:
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000
        response.headers["X-Request-ID"] = req_id
        if duration_ms > 3000:
            log.warning("[%s] SLOW %s %s%.0fms", req_id, request.method, request.url.path, duration_ms)
        else:
            log.info("[%s] <<< %s in %.0fms", req_id, response.status_code, duration_ms)
        return response
    except Exception as exc:
        duration_ms = (time.time() - start) * 1000
        log.exception(
            "[%s] !!! %s: %s after %.0fms",
            req_id,
            type(exc).__name__,
            exc,
            duration_ms,
        )
        raise
