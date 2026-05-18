import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.core.shutdown import shutdown_tracker

log = logging.getLogger(__name__)


class ShutdownGateMiddleware(BaseHTTPMiddleware):
    """关闭期间拒绝新请求。"""

    ALWAYS_ALLOW_PATHS = {"/api/health", "/api/health/"}

    async def dispatch(self, request: Request, call_next):
        if shutdown_tracker.is_shutting_down:
            if request.url.path in self.ALWAYS_ALLOW_PATHS:
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "shutting_down",
                        "active_streams": shutdown_tracker.active_count,
                    },
                )

            log.info(
                "Rejected new request during shutdown: %s %s",
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "服务正在关闭，请稍后重试",
                    "retry_after": 30,
                },
                headers={"Retry-After": "30"},
            )

        return await call_next(request)
