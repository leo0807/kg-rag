"""tests/test_ingest_task.py — unit tests for ingest_document Celery task"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tasks.ingest_tasks import _run


# ── helpers ──────────────────────────────────────────────────────────────────

DOC_ID = "doc-abc"
TMP_PATH = Path(f"/tmp/{DOC_ID}.pdf")  # matches stable_path so replace() is skipped


def _make_doc() -> MagicMock:
    doc = MagicMock()
    doc.doc_id = DOC_ID
    doc.total_sections = 3
    doc.pdf_path = None
    doc.sections = [
        MagicMock(chunk_id=f"c{i}", title=f"T{i}", content=f"content {i}")
        for i in range(3)
    ]
    return doc


def _make_driver(existing_count: int = 0) -> MagicMock:
    """Fake Neo4j driver; session.run().single()['cnt'] == existing_count."""
    record = MagicMock()
    record.__getitem__ = MagicMock(return_value=existing_count)
    session = MagicMock()
    session.run.return_value.single.return_value = record
    driver = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver


def _make_task() -> MagicMock:
    t = MagicMock()
    t.update_state = MagicMock()
    return t


def _base_patches(doc: MagicMock) -> list:
    """Minimal patches for the happy-path (new document, PDF)."""
    return [
        patch("src.tasks.ingest_tasks.parse", return_value=doc),
        patch("src.tasks.ingest_tasks.write_document"),
        patch("src.tasks.ingest_tasks.write_document_incremental", return_value={}),
        patch("src.tasks.ingest_tasks.run_image_analysis", new_callable=AsyncMock),
        patch("src.tasks.ingest_tasks.UPLOAD_DIR", Path("/tmp")),
    ]


# ── tests ─────────────────────────────────────────────────────────────────────

class TestIngestRun:

    @pytest.mark.asyncio
    async def test_new_doc_returns_done(self):
        """New document → written to graph → status=done."""
        doc = _make_doc()
        ps = _base_patches(doc)
        with ps[0], ps[1], ps[2], ps[3], ps[4]:
            result = await _run(_make_task(), TMP_PATH, _make_driver(0), incremental=False)

        assert result["status"] == "done"
        assert result["doc_id"] == DOC_ID
        assert result["sections"] == 3

    @pytest.mark.asyncio
    async def test_existing_doc_non_incremental_skipped(self):
        """Doc exists + incremental=False → skipped without writing."""
        doc = _make_doc()
        task = _make_task()
        ps = _base_patches(doc)
        with ps[0], ps[1], ps[2], ps[3], ps[4]:
            result = await _run(task, TMP_PATH, _make_driver(1), incremental=False)

        assert result["status"] == "skipped"
        assert result["doc_id"] == DOC_ID

    @pytest.mark.asyncio
    async def test_existing_doc_incremental_done(self):
        """Doc exists + incremental=True → incremental write → done."""
        doc = _make_doc()
        ps = _base_patches(doc)
        with ps[0], ps[1], ps[2], ps[3], ps[4]:
            result = await _run(_make_task(), TMP_PATH, _make_driver(1), incremental=True)

        assert result["status"] == "done"

    @pytest.mark.asyncio
    async def test_progress_steps_reported(self):
        """update_state is called for parsing and writing steps."""
        doc = _make_doc()
        task = _make_task()
        ps = _base_patches(doc)
        with ps[0], ps[1], ps[2], ps[3], ps[4]:
            await _run(task, TMP_PATH, _make_driver(0), incremental=False)

        reported = {c.kwargs["meta"]["step"] for c in task.update_state.call_args_list}
        assert "parsing" in reported
        assert "writing" in reported

    @pytest.mark.asyncio
    async def test_parse_failure_propagates(self):
        """parse() raising re-raises from _run so Celery marks FAILURE."""
        with patch("src.tasks.ingest_tasks.parse", side_effect=ValueError("bad pdf")), \
             patch("src.tasks.ingest_tasks.UPLOAD_DIR", Path("/tmp")):
            with pytest.raises(ValueError, match="bad pdf"):
                await _run(_make_task(), TMP_PATH, _make_driver(0), incremental=False)
