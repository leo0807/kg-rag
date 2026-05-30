"""Celery tasks for quality scanning and objective doc evaluation."""
from __future__ import annotations

import asyncio
import logging

from ..celery_app import celery_app
from ..services.infra.task_state import get_task_state_store
from ..tasks.driver_helpers import make_celery_driver

log = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_conflict_scan")
def run_conflict_scan(self, scan_id: str, entity_limit: int, constraint_limit: int) -> None:
    store = get_task_state_store()
    key = f"scan:conflict:{scan_id}"
    driver = make_celery_driver()
    try:
        store.update(key, refresh_ttl=True, status="running")
        from ..services.quality.conflict_scan import _run_scan
        asyncio.run(_run_scan(scan_id, driver, entity_limit, constraint_limit))
    except Exception as exc:
        log.exception("conflict_scan failed: scan_id=%s", scan_id)
        store.update(key, refresh_ttl=False, status="failed", error=str(exc))
        raise
    finally:
        driver.close()


@celery_app.task(bind=True, name="run_objective_doc_eval")
def run_objective_doc_eval(self, task_id: str, questions: list, strategy: str, top_k: int) -> None:
    store = get_task_state_store()
    key = f"eval:objective_doc:{task_id}"
    driver = make_celery_driver()
    try:
        store.update(key, refresh_ttl=True, status="running")
        from ..services.evaluation.objective_doc_eval_service import _persist_task, _now
        from ..services.evaluation.objective_doc_eval_runner import run_eval_task
        asyncio.run(run_eval_task(task_id, questions, strategy, top_k, driver, store, _persist_task, _now))
    except Exception as exc:
        log.exception("objective_doc_eval failed: task_id=%s", task_id)
        store.update(key, refresh_ttl=False, status="failed", error=str(exc))
        raise
    finally:
        driver.close()
