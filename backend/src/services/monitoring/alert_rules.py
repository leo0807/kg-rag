"""
Alert rules — evaluated periodically by the startup loop.
Each rule returns (should_fire: bool, message: str).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# Per-rule cooldown (seconds) — prevents alert storms
_RULE_COOLDOWN = 300
_last_fired: dict[str, float] = {}


@dataclass
class AlertRule:
    name: str
    level: str          # info / warning / error / critical
    title: str
    check: Callable[[], Awaitable[tuple[bool, str]]]
    cooldown: int = _RULE_COOLDOWN


async def _check_error_rate() -> tuple[bool, str]:
    """Fire if ≥50 errors in the last 5 minutes."""
    from ...db.session import AsyncSessionLocal
    from ...db.models import SystemErrorEvent
    from sqlalchemy import select, func
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
    try:
        async with AsyncSessionLocal() as db:
            count = (await db.execute(
                select(func.count(SystemErrorEvent.id))
                .where(SystemErrorEvent.created_at >= cutoff)
            )).scalar() or 0
        if count >= 50:
            return True, f"最近5分钟内发生 {count} 次服务错误"
        return False, ""
    except Exception:
        return False, ""


async def _check_llm_failure_rate() -> tuple[bool, str]:
    """Fire if LLM failure rate >10% over last 100 calls."""
    from ...db.session import AsyncSessionLocal
    from ...db.models import LLMUsage
    from sqlalchemy import select, func
    try:
        async with AsyncSessionLocal() as db:
            total = (await db.execute(
                select(func.count(LLMUsage.id))
                .order_by(LLMUsage.created_at.desc())
                .limit(100)
            )).scalar() or 0
            failed = (await db.execute(
                select(func.count(LLMUsage.id))
                .where(LLMUsage.error_type.isnot(None))
                .order_by(LLMUsage.created_at.desc())
                .limit(100)
            )).scalar() or 0
        if total >= 20 and failed / total > 0.10:
            return True, f"LLM API 失败率 {failed}/{total} ({failed/total:.0%})"
        return False, ""
    except Exception:
        return False, ""


async def _check_service_health() -> tuple[bool, str]:
    """Fire if any critical service is down."""
    from ...services.infra.health import health_monitor
    down = [
        name for name, status in health_monitor.to_dict().items()
        if status.get("state") == "down"
    ]
    if down:
        return True, f"服务不可用: {', '.join(down)}"
    return False, ""


async def _check_disk_usage() -> tuple[bool, str]:
    """Fire if disk usage >85%."""
    try:
        import shutil
        total, used, _ = shutil.disk_usage("/")
        pct = used / total
        if pct > 0.85:
            return True, f"磁盘使用率 {pct:.0%}，剩余 {(total-used)//1024//1024//1024} GB"
        return False, ""
    except Exception:
        return False, ""


async def _check_memory_usage() -> tuple[bool, str]:
    """Fire if memory usage >90%."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        if mem.percent > 90:
            return True, f"内存使用率 {mem.percent:.0f}%"
        return False, ""
    except Exception:
        return False, ""


RULES: list[AlertRule] = [
    AlertRule("error_rate",    "critical", "服务错误率过高",     _check_error_rate,     cooldown=300),
    AlertRule("llm_failures",  "critical", "LLM API 异常",       _check_llm_failure_rate, cooldown=600),
    AlertRule("service_down",  "critical", "依赖服务不可用",     _check_service_health, cooldown=120),
    AlertRule("disk_usage",    "warning",  "磁盘空间告警",       _check_disk_usage,     cooldown=3600),
    AlertRule("memory_usage",  "critical", "内存使用率告警",     _check_memory_usage,   cooldown=300),
]


async def evaluate_rules() -> None:
    """Run all rules; send alerts for those that fire."""
    from .alert_sender import alert_sender
    now = time.time()
    for rule in RULES:
        last = _last_fired.get(rule.name, 0)
        if now - last < rule.cooldown:
            continue
        try:
            fired, msg = await rule.check()
            if fired:
                _last_fired[rule.name] = now
                await alert_sender.alert(rule.level, rule.title, msg)  # type: ignore[arg-type]
        except Exception as e:
            logger.debug("规则 %s 检查失败: %s", rule.name, e)
