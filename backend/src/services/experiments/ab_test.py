"""
A/B test manager — assigns users to experiment variants deterministically
using MD5(user_id + experiment_name) mod 100 so the same user always gets
the same variant.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.ux_models import Experiment

logger = logging.getLogger(__name__)


class ABTestManager:
    async def get_variant(
        self,
        db: AsyncSession,
        experiment_name: str,
        user_id: str,
    ) -> Optional[str]:
        """Return the variant name for this user, or None if experiment not active."""
        row = await db.scalar(
            select(Experiment).where(
                Experiment.name == experiment_name,
                Experiment.status == "active",
            )
        )
        if not row:
            return None

        variants: list[dict] = row.variants or []
        if not variants:
            return None

        bucket = int(hashlib.md5(f"{user_id}:{experiment_name}".encode()).hexdigest(), 16) % 100
        cumulative = 0
        for v in variants:
            cumulative += int(v.get("weight", 0))
            if bucket < cumulative:
                return v.get("name")
        return variants[-1].get("name")

    async def record_metric(
        self,
        db: AsyncSession,
        experiment_name: str,
        variant: str,
        metric: str,
        value: float = 1.0,
    ) -> None:
        """Increment a metric counter for a variant."""
        row = await db.scalar(
            select(Experiment).where(Experiment.name == experiment_name)
        )
        if not row:
            return
        metrics: dict = dict(row.metrics or {})
        key = f"{variant}.{metric}"
        metrics[key] = metrics.get(key, 0) + value
        row.metrics = metrics
        await db.commit()


_manager: ABTestManager | None = None


def get_ab_manager() -> ABTestManager:
    global _manager
    if _manager is None:
        _manager = ABTestManager()
    return _manager
