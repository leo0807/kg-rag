"""
H1.2 集成基础抽象类
所有外部系统接入器的公共基类：认证、调用、日志、重试
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30
_MAX_RETRIES     = 3


class IntegrationError(Exception):
    def __init__(self, msg: str, status_code: int = 0):
        super().__init__(msg)
        self.status_code = status_code


class IntegrationProvider(ABC):
    """所有集成接入器的基类。外部系统故障时抛 IntegrationError，主流程捕获后降级。"""

    def __init__(self, integration_id: str, endpoint: str, auth_config: dict):
        self.integration_id = integration_id
        self.endpoint       = endpoint.rstrip("/")
        self.auth_config    = auth_config
        self._token: str | None = None

    # ── 子类必须实现 ──────────────────────────────────────────────────

    @abstractmethod
    async def test_connection(self) -> bool:
        """测试连接是否可用。"""

    @abstractmethod
    async def _get_auth_headers(self) -> dict[str, str]:
        """返回携带认证信息的 HTTP 头。"""

    # ── 统一调用入口 ──────────────────────────────────────────────────

    async def call(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: Any = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> Any:
        """带重试和日志的统一 HTTP 调用。"""
        url = f"{self.endpoint}{path}"
        headers = await self._get_auth_headers()
        start = time.monotonic()
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.request(
                        method, url, headers=headers,
                        params=params, json=json,
                    )
                duration_ms = int((time.monotonic() - start) * 1000)
                self._log(method, path, resp.status_code, duration_ms)

                if resp.status_code >= 400:
                    raise IntegrationError(
                        f"{method} {path} → HTTP {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                    )
                return resp.json()

            except IntegrationError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "integration call attempt %d/%d failed: %s %s → %s",
                    attempt, _MAX_RETRIES, method, path, exc,
                )

        raise IntegrationError(f"调用失败（{_MAX_RETRIES} 次重试）: {last_exc}")

    # ── 内部工具 ─────────────────────────────────────────────────────

    def _log(self, method: str, path: str, status: int, duration_ms: int) -> None:
        logger.info(
            "integration[%s] %s %s → %d (%dms)",
            self.integration_id, method, path, status, duration_ms,
        )


# ── 常用认证实现 ──────────────────────────────────────────────────────

class ApiKeyProvider(IntegrationProvider, ABC):
    """X-API-Key 头认证。"""

    async def _get_auth_headers(self) -> dict[str, str]:
        key = self.auth_config.get("api_key", "")
        header_name = self.auth_config.get("header_name", "X-API-Key")
        return {header_name: key}

    async def test_connection(self) -> bool:
        try:
            await self.call("GET", self.auth_config.get("health_path", "/health"))
            return True
        except IntegrationError:
            return False


class BasicAuthProvider(IntegrationProvider, ABC):
    """HTTP Basic 认证。"""

    async def _get_auth_headers(self) -> dict[str, str]:
        import base64
        u = self.auth_config.get("username", "")
        p = self.auth_config.get("password", "")
        token = base64.b64encode(f"{u}:{p}".encode()).decode()
        return {"Authorization": f"Basic {token}"}

    async def test_connection(self) -> bool:
        try:
            await self.call("GET", self.auth_config.get("health_path", "/health"))
            return True
        except IntegrationError:
            return False


def build_provider(integration: Any) -> IntegrationProvider | None:
    """根据集成记录动态构建接入器（工厂函数）。"""
    from .plm_provider import PLMProvider
    from .mes_provider import MESProvider
    from .erp_provider import ERPProvider

    mapping = {"plm": PLMProvider, "mes": MESProvider, "erp": ERPProvider}
    cls = mapping.get(integration.type)
    if cls is None:
        return None
    return cls(
        integration_id=integration.id,
        endpoint=integration.endpoint or "",
        auth_config=integration.auth_config or {},
    )
