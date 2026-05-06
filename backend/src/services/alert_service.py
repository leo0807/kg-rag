"""
services/alert_service.py
钉钉 / 企业微信告警推送，含同类告警冷却去重。
"""
from __future__ import annotations

import logging
import time
from typing import ClassVar

import aiohttp

logger = logging.getLogger(__name__)

_EMOJIS = {"info": "ℹ️", "warning": "⚠️", "error": "🔴"}


class AlertService:
    """
    单例告警服务，支持钉钉 Markdown 和企业微信 Markdown 两种渠道。
    同一 title 的告警在 cooldown 期内只推送一次（通过内存时间戳去重）。
    """

    _instance: ClassVar["AlertService | None"] = None

    def __new__(cls) -> "AlertService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self) -> None:
        self._last_sent: dict[str, float] = {}

    # ── 推送 ──────────────────────────────────────────────────────────────────

    async def send_alert(
        self,
        title: str,
        content: str,
        level: str = "info",
    ) -> None:
        from .runtime.model_settings import get_runtime_settings_namespace
        runtime = get_runtime_settings_namespace()

        dingtalk = getattr(runtime, "DINGTALK_WEBHOOK", "") or ""
        wecom    = getattr(runtime, "WECOM_WEBHOOK", "") or ""
        cooldown = int(getattr(runtime, "ALERT_COOLDOWN_MINUTES", "30") or "30") * 60

        if not dingtalk and not wecom:
            logger.debug("告警渠道未配置，跳过推送: %s", title)
            return

        now = time.time()
        last = self._last_sent.get(title, 0)
        if now - last < cooldown:
            logger.debug("告警冷却中，跳过: %s (剩余 %.0fs)", title, cooldown - (now - last))
            return
        self._last_sent[title] = now

        emoji = _EMOJIS.get(level, "ℹ️")
        message = f"{emoji} **{title}**\n\n{content}"

        if dingtalk:
            await self._send_dingtalk(dingtalk, message)
        if wecom:
            await self._send_wecom(wecom, message)

    async def _send_dingtalk(self, webhook: str, message: str) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(
                    webhook,
                    json={
                        "msgtype": "markdown",
                        "markdown": {"title": "CPS知识库告警", "text": message},
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                )
                data = await resp.json()
                if data.get("errcode", 0) != 0:
                    logger.warning("钉钉告警推送失败: %s", data)
        except Exception as e:
            logger.warning("钉钉告警推送异常: %s", e)

    async def _send_wecom(self, webhook: str, message: str) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.post(
                    webhook,
                    json={"msgtype": "markdown", "markdown": {"content": message}},
                    timeout=aiohttp.ClientTimeout(total=10),
                )
                data = await resp.json()
                if data.get("errcode", 0) != 0:
                    logger.warning("企业微信告警推送失败: %s", data)
        except Exception as e:
            logger.warning("企业微信告警推送异常: %s", e)


# 全局单例
alert_service = AlertService()
