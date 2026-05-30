"""Celery tasks for evaluation services.

Each task wraps the async _run_xxx function with asyncio.run(),
updates Redis TTL at task entry (refresh_ttl=True) and relies on
the runner to set final status at completion.
"""
from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

from ..celery_app import celery_app
from .driver_helpers import make_celery_driver
from ..services.infra.task_state import get_task_state_store

log = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_faithfulness_eval")
def run_faithfulness_eval(self, task_id: str, rows: list) -> None:
    store = get_task_state_store()
    key = f"eval:faithfulness:{task_id}"
    try:
        store.update(key, refresh_ttl=True, status="running")
        from ..services.evaluation.faithfulness_service import _run_faithfulness_task
        asyncio.run(_run_faithfulness_task(task_id, rows))
    except Exception as exc:
        log.exception("faithfulness eval failed: task_id=%s", task_id)
        store.update(key, refresh_ttl=False, status="failed", error=str(exc))
        raise


@celery_app.task(bind=True, name="run_dataset_eval")
def run_dataset_eval(
    self,
    task_id: str,
    rows: list,
    strategy: str,
    top_k: int,
    user_id: str,
) -> None:
    store = get_task_state_store()
    key = f"eval:dataset:{task_id}"
    driver = make_celery_driver()
    try:
        store.update(key, refresh_ttl=True, status="running")
        user = SimpleNamespace(id=user_id, department="")
        from ..services.evaluation.dataset_eval_service import _run_task as _run_dataset_task
        asyncio.run(_run_dataset_task(task_id, rows, strategy, top_k, driver, user))
    except Exception as exc:
        log.exception("dataset eval failed: task_id=%s", task_id)
        store.update(key, refresh_ttl=False, status="failed", error=str(exc))
        raise
    finally:
        driver.close()


@celery_app.task(bind=True, name="run_retrieval_harness")
def run_retrieval_harness(self, task_id: str, rows: list, strategy: str, top_k: int) -> None:
    store = get_task_state_store()
    key = f"eval:retrieval:{task_id}"
    driver = make_celery_driver()
    try:
        store.update(key, refresh_ttl=True, status="running")
        from ..services.evaluation.retrieval_harness_service import _run_task as _run_retrieval_task
        asyncio.run(_run_retrieval_task(task_id, rows, strategy, top_k, driver))
    except Exception as exc:
        log.exception("retrieval harness failed: task_id=%s", task_id)
        store.update(key, refresh_ttl=False, status="failed", error=str(exc))
        raise
    finally:
        driver.close()


@celery_app.task(bind=True, name="run_ab_test")
def run_ab_test(self, task_id: str, rows: list, strategies: list, top_k: int) -> None:
    store = get_task_state_store()
    key = f"eval:ab:{task_id}"
    driver = make_celery_driver()
    try:
        store.update(key, refresh_ttl=True, status="running")
        from ..services.evaluation.ab_test_service import _run_ab_task
        asyncio.run(_run_ab_task(task_id, rows, strategies, top_k, driver))
    except Exception as exc:
        log.exception("ab test failed: task_id=%s", task_id)
        store.update(key, refresh_ttl=False, status="failed", error=str(exc))
        raise
    finally:
        driver.close()
