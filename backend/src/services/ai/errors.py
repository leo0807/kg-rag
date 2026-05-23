from __future__ import annotations

"""Shared LLM error mapping helpers."""

import re


class LLMError(Exception):
    """LLM 调用失败，携带用户可见的错误码和消息。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int | None = None,
        endpoint: str = "",
        provider_code: int | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.endpoint = endpoint
        self.provider_code = provider_code


def trim_preview(text: str, limit: int = 400) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def classify_llm_error(status: int, response_text: str = "", model: str = "") -> LLMError:
    """将 HTTP 状态码 + 响应体映射为 LLMError，供 map_exception 和单元测试复用。"""
    if status == 401:
        return LLMError("auth_failed", "API key 无效或已失效", status_code=401)

    if status == 403:
        body = (response_text or "").lower()
        if "model disabled" in body or "model not found" in body or re.search(r"model.*unavailable", body):
            return LLMError(
                "model_unavailable",
                f"LLM 模型不可用，请检查配置或更换模型(model={model})",
                status_code=403,
            )
        if any(kw in body for kw in ("quota", "额度", "balance", "余额", "insufficient")):
            return LLMError("quota_exceeded", "API 额度不足，请联系管理员充值", status_code=403)
        excerpt = response_text[:200] if response_text else "(no body)"
        return LLMError("forbidden", f"LLM 服务拒绝访问: {excerpt}", status_code=403)

    if status == 429:
        return LLMError("rate_limited", "调用频率超限，请稍后重试", status_code=429)

    if status in (408, 504):
        return LLMError("timeout", "模型响应超时，请重试", status_code=status)

    return LLMError("unknown_error", "AI 服务异常，请联系管理员", status_code=status)


def parse_response_for_business_error(data: dict) -> LLMError | None:
    """检测 HTTP 200 响应体中隐藏的业务错误码（OpenAI 兼容 provider 特性）。
    返回 LLMError 表示有错误，返回 None 表示正常。
    """
    if not isinstance(data, dict) or "choices" in data:
        return None
    code = data.get("code")
    if code in (0, None, "0"):
        return None
    message = data.get("message", "unknown")
    try:
        provider_code = int(code)
    except (TypeError, ValueError):
        provider_code = None
    return LLMError(
        "api_invalid_request",
        f"LLM API 拒绝请求: {message}",
        status_code=200,
        provider_code=provider_code,
    )


def map_exception(exc: Exception, endpoint: str = "", model: str = "") -> LLMError:
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
    response_text: str = ""
    if isinstance(exc, _req_http) and getattr(exc, "response", None) is not None:
        status = exc.response.status_code  # type: ignore[union-attr]
        try:
            response_text = exc.response.text  # type: ignore[union-attr]
        except Exception:
            pass
    elif isinstance(exc, _hx_http):
        status = exc.response.status_code  # type: ignore[union-attr]
        try:
            response_text = exc.response.text  # type: ignore[union-attr]
        except Exception:
            pass

    if status is not None:
        err = classify_llm_error(status, response_text, model)
        err.endpoint = endpoint
        return err

    if isinstance(exc, (_req_to, _hx_to)):
        return LLMError("timeout", "模型响应超时，请重试", endpoint=endpoint)
    if isinstance(exc, (_req_conn, _hx_conn)):
        return LLMError("service_unavailable", "AI 服务暂时不可用，请稍后再试", endpoint=endpoint)

    return LLMError("unknown_error", "AI 服务异常，请联系管理员", endpoint=endpoint)
