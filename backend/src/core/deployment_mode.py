"""
I1: Deployment mode detection and validation for offline/private deployments.
"""
from __future__ import annotations

import logging
import socket
from enum import Enum
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

_EXTERNAL_PROBE_HOSTS = [
    ("8.8.8.8", 53),
    ("1.1.1.1", 53),
]


class DeploymentMode(str, Enum):
    CLOUD     = "cloud"      # fully cloud-based
    HYBRID    = "hybrid"     # some external APIs allowed
    INTRANET  = "intranet"   # intranet: local LLM only
    AIRGAPPED = "airgapped"  # completely isolated


class DeploymentChecker:
    """Validates environment readiness for offline / private deployments."""

    def __init__(self) -> None:
        self._mode: DeploymentMode | None = None

    # ── mode detection ──────────────────────────────────────────────────

    async def detect_mode(self) -> DeploymentMode:
        """Resolve mode from settings; fall back to CLOUD."""
        from .config import settings
        try:
            mode = DeploymentMode(settings.DEPLOYMENT_MODE)
        except ValueError:
            logger.warning("未知 DEPLOYMENT_MODE=%s，回退 cloud", settings.DEPLOYMENT_MODE)
            mode = DeploymentMode.CLOUD
        self._mode = mode
        return mode

    @property
    def mode(self) -> DeploymentMode:
        return self._mode or DeploymentMode.CLOUD

    # ── offline readiness ────────────────────────────────────────────────

    async def validate_offline_ready(self) -> Dict[str, Any]:
        """Run all offline prerequisite checks and return a result map."""
        results: Dict[str, Any] = {
            "local_llm_available":  await self._check_local_llm(),
            "no_external_calls":    self._check_no_external_dns(),
            "local_storage_ready":  self._check_storage(),
            "local_models_present": await self._check_local_llm(),  # proxy check
        }
        results["all_ok"] = all(v for v in results.values())
        return results

    async def enforce_airgap(self) -> None:
        """Called at startup for AIRGAPPED mode; raises RuntimeError on failure."""
        results = await self.validate_offline_ready()
        failed = [k for k, v in results.items() if k != "all_ok" and not v]
        if failed:
            raise RuntimeError(
                f"AIRGAPPED 模式启动失败，以下检查未通过: {failed}。"
                "请确保本地 LLM（Ollama/vLLM）已启动，并且 LLM_API_URL 指向本地服务。"
            )
        logger.info("离线模式验证通过 ✓")

    # ── individual checks ────────────────────────────────────────────────

    async def _check_local_llm(self) -> bool:
        from .config import settings
        base = settings.LLM_API_URL.rstrip("/")
        # Remove /v1 suffix to get the root URL
        root = base[:-3] if base.endswith("/v1") else base
        probes = [
            f"{root}/api/tags",      # Ollama
            f"{base}/models",        # OpenAI-compat (vLLM/TGI)
        ]
        async with httpx.AsyncClient(timeout=4.0) as client:
            for url in probes:
                try:
                    r = await client.get(url)
                    if r.status_code < 500:
                        return True
                except Exception:
                    pass
        return False

    def _check_no_external_dns(self) -> bool:
        """True when external internet is unreachable (expected in airgapped mode)."""
        if self.mode not in (DeploymentMode.AIRGAPPED, DeploymentMode.INTRANET):
            return True  # not required for cloud/hybrid
        for host, port in _EXTERNAL_PROBE_HOSTS:
            try:
                sock = socket.create_connection((host, port), timeout=1.5)
                sock.close()
                return False  # external reachable — isolation broken
            except OSError:
                pass
        return True

    def _check_storage(self) -> bool:
        try:
            import shutil
            _, _, free = shutil.disk_usage("/")
            return free > 20 * 1024 ** 3  # 20 GB minimum
        except Exception:
            return True  # non-fatal


# Module-level singleton
deployment_checker = DeploymentChecker()
