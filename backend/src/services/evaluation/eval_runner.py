"""
Eval runner — orchestrates a structured EvalRun using the existing
objective_doc_eval_runner infrastructure for actual question answering.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.eval_models import EvalDataset, EvalQuestion, EvalResult, EvalRun
from ...db.session import AsyncSessionLocal
from .eval_config import EvalRunConfig

logger = logging.getLogger(__name__)

# In-memory run cancellation flags
_CANCEL_FLAGS: dict[str, bool] = {}


async def _answer_one(
    question: EvalQuestion,
    config: EvalRunConfig,
    driver: Any,
) -> dict:
    from .objective_doc_eval_runner import answer_objective_question
    start = time.time()
    try:
        opts: list[dict] = []
        if question.options:
            opts = [{"label": k, "text": v} for k, v in question.options.items()]
        result = answer_objective_question(
            question=question.stem,
            options=opts,
            question_type=question.question_type,
            answer_key=question.correct_answer,
            strategy=config.strategy,
            top_k=config.top_k,
            driver=driver,
            doc_id=config.source_doc_id or question.source_doc_id or "",
        )
        predicted = str(result.get("predicted_answer", "")).strip()
        correct_ans = question.correct_answer.strip().upper()
        predicted_up = predicted.upper()
        is_correct = (predicted_up == correct_ans or
                      correct_ans in predicted_up or
                      predicted_up in correct_ans)
        return {
            "predicted_answer": predicted,
            "is_correct":       is_correct,
            "reasoning":        str(result.get("reason", ""))[:500],
            "sources":          result.get("source_refs", []),
            "latency_ms":       int((time.time() - start) * 1000),
            "error_type":       "" if predicted else "no_answer",
        }
    except Exception as e:
        logger.warning("question %s failed: %s", question.id, e)
        return {
            "predicted_answer": "", "is_correct": False,
            "reasoning": str(e)[:200], "sources": [],
            "latency_ms": int((time.time() - start) * 1000),
            "error_type": type(e).__name__,
        }


def _compute_metrics(results: list[dict], questions: list[EvalQuestion]) -> dict:
    if not results:
        return {}
    correct = sum(1 for r in results if r.get("is_correct"))
    accuracy = correct / len(results)

    latencies = [r["latency_ms"] for r in results if r.get("latency_ms")]
    latencies_sorted = sorted(latencies) if latencies else [0]

    # per-type accuracy
    by_type: dict[str, list[bool]] = {}
    for q, r in zip(questions, results):
        by_type.setdefault(q.question_type, []).append(r.get("is_correct", False))
    accuracy_by_type = {
        t: round(sum(v)/len(v), 4) for t, v in by_type.items()
    }

    return {
        "accuracy":         round(accuracy, 4),
        "accuracy_by_type": accuracy_by_type,
        "avg_latency_ms":   round(statistics.mean(latencies) if latencies else 0, 1),
        "p95_latency_ms":   round(latencies_sorted[int(len(latencies_sorted) * 0.95)] if latencies else 0, 1),
    }


async def start_eval_run(config: EvalRunConfig, user_id: str) -> str:
    """Create the run record and launch the background task. Returns run_id."""
    run_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as db:
        ds = await db.get(EvalDataset, config.dataset_id)
        if not ds:
            raise ValueError(f"Dataset {config.dataset_id} not found")
        total = (await db.execute(
            select(EvalQuestion).where(EvalQuestion.dataset_id == config.dataset_id)
        )).scalars().all()

        run = EvalRun(
            id=run_id,
            run_name=config.run_name or f"{config.strategy}-{datetime.utcnow().strftime('%m%d%H%M')}",
            description=config.description,
            dataset_id=config.dataset_id,
            config=config.to_dict(),
            status="running",
            total_questions=len(total),
            tags=config.tags,
            started_at=datetime.utcnow(),
            created_by=user_id,
        )
        db.add(run)
        await db.commit()

    _CANCEL_FLAGS[run_id] = False
    asyncio.create_task(_run_task(run_id, config, len(total)))
    return run_id


async def _run_task(run_id: str, config: EvalRunConfig, total: int) -> None:
    from ...core.database import get_driver
    driver = get_driver()
    semaphore = asyncio.Semaphore(config.concurrency)

    async with AsyncSessionLocal() as db:
        questions = (await db.execute(
            select(EvalQuestion).where(EvalQuestion.dataset_id == config.dataset_id)
                                .order_by(EvalQuestion.order_index)
        )).scalars().all()

    results: list[dict] = []
    completed = 0

    async def _bounded(q: EvalQuestion) -> dict:
        nonlocal completed
        async with semaphore:
            if _CANCEL_FLAGS.get(run_id):
                return {"predicted_answer": "", "is_correct": False,
                        "reasoning": "cancelled", "sources": [], "latency_ms": 0, "error_type": "cancelled"}
            r = await asyncio.wait_for(
                asyncio.to_thread(_answer_one_sync, q, config, driver),
                timeout=config.timeout_per_question,
            )
            completed += 1
            # Persist result immediately
            async with AsyncSessionLocal() as _db:
                _db.add(EvalResult(
                    id=str(uuid.uuid4()), run_id=run_id, question_id=q.id,
                    **r,
                ))
                run_row = await _db.get(EvalRun, run_id)
                if run_row:
                    run_row.completed_questions = completed
                    run_row.progress = int(completed / total * 100)
                await _db.commit()
            return r

    tasks = [_bounded(q) for q in questions]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    for item in raw:
        if isinstance(item, Exception):
            results.append({"is_correct": False, "latency_ms": 0, "error_type": str(item)})
        else:
            results.append(item)

    metrics = _compute_metrics(results, list(questions))

    async with AsyncSessionLocal() as db:
        run_row = await db.get(EvalRun, run_id)
        if run_row:
            cancelled = _CANCEL_FLAGS.get(run_id, False)
            run_row.status = "cancelled" if cancelled else "completed"
            run_row.completed_at = datetime.utcnow()
            for k, v in metrics.items():
                if hasattr(run_row, k):
                    setattr(run_row, k, v)
            await db.commit()

    _CANCEL_FLAGS.pop(run_id, None)
    logger.info("eval run %s finished: accuracy=%.2f", run_id, metrics.get("accuracy", 0))


def _answer_one_sync(q: EvalQuestion, config: EvalRunConfig, driver: Any) -> dict:
    """Synchronous wrapper — runs in a thread."""
    import asyncio as _asyncio
    loop = _asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_answer_one(q, config, driver))
    finally:
        loop.close()


def cancel_run(run_id: str) -> None:
    _CANCEL_FLAGS[run_id] = True
