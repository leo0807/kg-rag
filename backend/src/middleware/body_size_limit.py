import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

log = logging.getLogger(__name__)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """
    全局请求体大小限制中间件（L1 兜底保护）。
    Content-Length 头超出阈值的请求直接拒绝，不消耗 stream。
    无 Content-Length 头的请求（如分块传输）不在此层拦截，由 L2 业务层兜底。
    """

    def __init__(self, app, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        if request.method not in ("POST", "PUT", "PATCH"):
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_bytes:
                    log.warning(
                        "Body too large: %d > %d on %s",
                        size, self.max_bytes, request.url.path,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": (
                                f"请求体过大（{size} bytes），"
                                f"上限 {self.max_bytes} bytes"
                            )
                        },
                    )
            except ValueError:
                pass

        return await call_next(request)
