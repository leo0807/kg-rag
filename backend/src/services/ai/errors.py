from __future__ import annotations

"""Shared LLM error mapping helpers."""


class LLMError(Exception):
    """LLM 调用失败，携带用户可见的错误码和消息。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int | None = None,
        endpoint: str = "",
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.endpoint = endpoint


def trim_preview(text: str, limit: int = 400) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def map_exception(exc: Exception, endpoint: str = "") -> LLMError:
    """将底层异常映射为 LLMError，便于上层统一处理。"""
    try:
        import requests as _req

        _req_http = _req.HTTPError
        _req_to = _req.exceptions.Timeout
        _req_conn = _req.exceptions.ConnectionError
    except ImportError:
        _req_http = _req_to = _req_conn = type(None)  # type: ignore[assignment]

    try:
        import httpx as _httpx

        _hx_http = _httpx.HTTPStatusError
        _hx_to = _httpx.TimeoutException
        _hx_conn = _httpx.ConnectError
    except ImportError:
        _hx_http = _hx_to = _hx_conn = type(None)  # type: ignore[assignment]

    if isinstance(exc, LLMError):
        return exc

    status: int | None = None
    if isinstance(exc, _req_http) and getattr(exc, "response", None) is not None:
        status = exc.response.status_code  # type: ignore[union-attr]
    elif isinstance(exc, _hx_http):
        status = exc.response.status_code  # type: ignore[union-attr]

    if status == 403:
        return LLMError("quota_exceeded", "API 额度不足，请联系管理员充值", status_code=status, endpoint=endpoint)
    if status == 429:
        return LLMError("rate_limited", "请求过于频繁，请稍后再试", status_code=status, endpoint=endpoint)
    if status in (408, 504):
        return LLMError("timeout", "模型响应超时，请重试", status_code=status, endpoint=endpoint)
    if status is not None:
        return LLMError("unknown_error", "AI 服务异常，请联系管理员", status_code=status, endpoint=endpoint)

    if isinstance(exc, (_req_to, _hx_to)):
        return LLMError("timeout", "模型响应超时，请重试", endpoint=endpoint)
    if isinstance(exc, (_req_conn, _hx_conn)):
        return LLMError("service_unavailable", "AI 服务暂时不可用，请稍后再试", endpoint=endpoint)

    return LLMError("unknown_error", "AI 服务异常，请联系管理员", endpoint=endpoint)

