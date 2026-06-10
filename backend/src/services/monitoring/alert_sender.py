"""
Unified alert sender — wraps the existing AlertService with
level-aware routing (critical→all channels, warning→webhook, info→log only)
and email support.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText
from typing import Literal

logger = logging.getLogger(__name__)

Level = Literal["info", "warning", "error", "critical"]


class AlertSender:
    """
    Unified multi-channel alert sender.

    Routing table:
      critical → dingtalk/wecom + email
      error    → dingtalk/wecom
      warning  → dingtalk/wecom
      info     → log only
    """

    async def send_dingtalk(self, message: str, level: Level = "info") -> None:
        from ..alert_service import alert_service
        await alert_service.send_alert(f"[{level.upper()}]", message, level=level)

    async def send_wecom(self, message: str, level: Level = "info") -> None:
        # alert_service sends to both channels; this is a convenience alias
        await self.send_dingtalk(message, level)

    async def send_email(self, to: str, subject: str, body: str) -> None:
        from ...core.config import settings
        smtp_host = getattr(settings, "SMTP_HOST", "")
        smtp_port = int(getattr(settings, "SMTP_PORT", "587") or "587")
        smtp_user = getattr(settings, "SMTP_USER", "")
        smtp_pass = getattr(settings, "SMTP_PASS", "")

        if not smtp_host or not smtp_user:
            logger.debug("SMTP 未配置，跳过邮件: %s", subject)
            return
        try:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"]    = smtp_user
            msg["To"]      = to
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as srv:
                srv.starttls()
                srv.login(smtp_user, smtp_pass)
                srv.send_message(msg)
            logger.info("邮件告警已发送至 %s: %s", to, subject)
        except Exception as e:
            logger.warning("邮件发送失败: %s", e)

    async def alert(
        self,
        level: Level,
        title: str,
        content: str,
        channels: list[str] | None = None,
    ) -> None:
        """
        Unified entry point.
        channels: ["dingtalk", "wecom", "email"] — None means auto-select by level.
        """
        full_msg = f"**{title}**\n\n{content}"

        if level == "info":
            logger.info("[告警] %s: %s", title, content)
            return

        logger.warning("[告警-%s] %s: %s", level.upper(), title, content)

        auto_webhook = level in ("warning", "error", "critical")
        auto_email   = level == "critical"

        use_webhook = channels is None and auto_webhook or (channels and "dingtalk" in channels)
        use_email   = channels is None and auto_email   or (channels and "email" in channels)

        if use_webhook:
            try:
                await self.send_dingtalk(full_msg, level)
            except Exception as e:
                logger.warning("Webhook 告警失败: %s", e)

        if use_email:
            from ...core.config import settings
            admin_email = getattr(settings, "ADMIN_EMAIL", "")
            if admin_email:
                try:
                    await self.send_email(admin_email, f"[CPS告警] {title}", content)
                except Exception as e:
                    logger.warning("邮件告警失败: %s", e)


# 全局单例
alert_sender = AlertSender()
