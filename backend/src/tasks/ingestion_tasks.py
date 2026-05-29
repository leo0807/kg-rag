"""F122-C: backfill and batch ingest Celery tasks"""
import asyncio
import logging
from pathlib import Path

from ..celery_app import celery_app
from .driver_helpers import make_celery_driver

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_backfill")
def run_backfill(self, doc_ids: list) -> dict:
    """Run image backfill for the given document IDs."""
    from ..services.ingestion.backfill_runtime import _backfill_loop

    driver = make_celery_driver()
    try:
        asyncio.run(_backfill_loop(doc_ids, driver))
        return {"status": "done", "count": len(doc_ids)}
    finally:
        driver.close()


@celery_app.task(bind=True, name="run_batch_ingest")
def run_batch_ingest(self, file_paths: list) -> dict:
    """Run batch document ingestion for the given file paths."""
    from ..services.ingestion.batch_ingest_service import _ingest_loop

    driver = make_celery_driver()
    try:
        paths = [Path(p) for p in file_paths]
        asyncio.run(_ingest_loop(paths, driver))
        return {"status": "done", "count": len(file_paths)}
    finally:
        driver.close()
