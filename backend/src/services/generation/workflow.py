"""
规范生成工作流编排器 — 按章节顺序生成，写入 DB，支持进度追踪。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from ...core.database import get_driver
from ...db.gen_models import GenerationTask
from ...db.session import AsyncSessionLocal
from .section_generator import SectionGenerator, _retrieve_section_content
from .validator import SpecValidator

logger = logging.getLogger(__name__)

# ── 进度表：(section_num, display_name, progress_after) ─────────────────────
SECTION_PLAN = [
    ("1", "范围章节",     15),
    ("2", "引用文件",     25),
    ("3", "术语和定义",   35),
    ("4", "材料",         45),
    ("6", "技术要求",     60),
    ("7", "工艺规程",     75),
    ("8", "检验与试验",   88),
    ("9", "标识与记录",   95),
]


class SpecGenerationWorkflow:
    """异步规范生成工作流，通过 asyncio.create_task 在后台运行。"""

    async def _update(
        self,
        task_id: str,
        progress: int,
        step: str,
        status: str = "running",
        sections: dict | None = None,
        error: str = "",
    ) -> None:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(GenerationTask).where(GenerationTask.id == task_id)
            )
            task = result.scalar_one_or_none()
            if not task:
                return
            task.progress    = progress
            task.current_step = step
            task.status      = status
            if error:
                task.error   = error[:1000]
            if sections is not None:
                task.result_sections = sections
            if status in ("done", "failed"):
                task.completed_at = datetime.utcnow().isoformat()
            await db.commit()

    async def run(self, task_id: str) -> None:
        logger.info("[WORKFLOW] 开始生成任务 %s", task_id)

        # 1. 加载任务
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(GenerationTask).where(GenerationTask.id == task_id)
            )
            task = result.scalar_one_or_none()
        if not task:
            logger.error("[WORKFLOW] 任务 %s 不存在", task_id)
            return

        inputs = task.inputs or {}
        sections: dict[str, str] = {}

        try:
            driver = get_driver()
        except Exception:
            driver = None

        gen = SectionGenerator(driver=driver)
        doc_ids = inputs.get("reference_docs", [])

        try:
            for sec_num, sec_name, progress_after in SECTION_PLAN:
                await self._update(task_id, progress_after - 10, f"生成 §{sec_num} {sec_name}")
                logger.info("[WORKFLOW] 生成 §%s %s", sec_num, sec_name)

                try:
                    content = await gen.generate_section_by_number(sec_num, inputs, sections)
                    sections[sec_num] = content
                    await self._update(task_id, progress_after, f"§{sec_num} 完成", sections=sections)
                except Exception as e:
                    logger.warning("[WORKFLOW] §%s 生成失败: %s", sec_num, e)
                    sections[sec_num] = f"（§{sec_num} 生成失败: {e}）"

            # 2. 自检校验
            await self._update(task_id, 96, "执行自检校验", sections=sections)
            validator = SpecValidator()
            report = validator.validate_full(sections, inputs, doc_ids)

            # 3. 完成
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                result = await db.execute(
                    select(GenerationTask).where(GenerationTask.id == task_id)
                )
                t = result.scalar_one_or_none()
                if t:
                    t.progress          = 100
                    t.current_step      = "生成完成"
                    t.status            = "done"
                    t.result_sections   = sections
                    t.validation_report = report
                    t.completed_at      = datetime.utcnow().isoformat()
                    await db.commit()

            logger.info("[WORKFLOW] 任务 %s 完成，%d 个章节", task_id, len(sections))

        except Exception as e:
            logger.exception("[WORKFLOW] 任务 %s 异常: %s", task_id, e)
            await self._update(task_id, 0, "生成失败", status="failed", error=str(e))

    async def regenerate_section(self, task_id: str, section_num: str) -> None:
        """重新生成单个章节，不影响其他章节。"""
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(GenerationTask).where(GenerationTask.id == task_id)
            )
            task = result.scalar_one_or_none()
        if not task:
            return

        inputs = task.inputs or {}
        existing = dict(task.result_sections or {})

        try:
            driver = get_driver()
        except Exception:
            driver = None

        gen = SectionGenerator(driver=driver)
        await self._update(task_id, task.progress, f"重新生成 §{section_num}")
        try:
            content = await gen.generate_section_by_number(section_num, inputs, existing)
            existing[section_num] = content
            # Re-validate
            validator = SpecValidator()
            report = validator.validate_full(existing, inputs, inputs.get("reference_docs", []))
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                result = await db.execute(
                    select(GenerationTask).where(GenerationTask.id == task_id)
                )
                t = result.scalar_one_or_none()
                if t:
                    t.result_sections   = existing
                    t.validation_report = report
                    t.current_step      = f"§{section_num} 重新生成完成"
                    await db.commit()
        except Exception as e:
            logger.error("[WORKFLOW] 重新生成 §%s 失败: %s", section_num, e)
