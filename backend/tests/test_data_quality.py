"""
Unit tests for src/services/governance/data_quality.py
Uses AsyncMock to simulate DB results without a real database.
Runs async tests via asyncio.run() since pytest-asyncio is not installed.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock


def _make_scalar(value):
    result = MagicMock()
    result.scalar.return_value = value
    result.fetchall = MagicMock(return_value=[])
    return result


def _db_all_zeros():
    db = AsyncMock()
    db.execute.return_value = _make_scalar(0)
    return db


# ── check_document_quality ────────────────────────────────────────────────────

def test_check_document_quality_no_issues():
    from src.services.governance.data_quality import check_document_quality
    db = _db_all_zeros()
    issues = asyncio.run(check_document_quality(db))
    assert isinstance(issues, list)
    assert issues == []


def test_check_document_quality_empty_content_issue():
    from src.services.governance.data_quality import check_document_quality

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        result.fetchall = MagicMock(return_value=[])
        if call_count == 1:
            result.scalar.return_value = 3  # empty_content
        elif call_count == 2:
            result.scalar.return_value = 0  # no_title
        else:
            result.fetchall.return_value = []
        return result

    db = AsyncMock()
    db.execute.side_effect = side_effect
    issues = asyncio.run(check_document_quality(db))
    types = [i["type"] for i in issues]
    assert "empty_content" in types


def test_check_document_quality_missing_title_issue():
    from src.services.governance.data_quality import check_document_quality

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        result.fetchall = MagicMock(return_value=[])
        if call_count == 1:
            result.scalar.return_value = 0
        elif call_count == 2:
            result.scalar.return_value = 5  # missing titles
        else:
            pass
        return result

    db = AsyncMock()
    db.execute.side_effect = side_effect
    issues = asyncio.run(check_document_quality(db))
    assert any(i["type"] == "missing_title" for i in issues)


def test_check_document_quality_duplicate_filenames():
    from src.services.governance.data_quality import check_document_quality

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count <= 2:
            result.scalar.return_value = 0
            result.fetchall = MagicMock(return_value=[])
        else:
            result.scalar.return_value = 0
            result.fetchall = MagicMock(return_value=[("file.pdf", 2), ("doc.pdf", 3)])
        return result

    db = AsyncMock()
    db.execute.side_effect = side_effect
    issues = asyncio.run(check_document_quality(db))
    assert any(i["type"] == "duplicate_filename" for i in issues)


def test_check_document_quality_db_error_returns_empty():
    from src.services.governance.data_quality import check_document_quality

    db = AsyncMock()
    db.execute.side_effect = Exception("DB connection failed")
    issues = asyncio.run(check_document_quality(db))
    assert issues == []


# ── get_quality_summary ───────────────────────────────────────────────────────

def test_get_quality_summary_structure():
    from src.services.governance.data_quality import get_quality_summary

    db = _db_all_zeros()
    summary = asyncio.run(get_quality_summary(db))
    assert "checked_at" in summary
    assert "issues" in summary
    assert "total_issues" in summary
    assert "severity_counts" in summary


def test_get_quality_summary_severity_keys():
    from src.services.governance.data_quality import get_quality_summary

    db = _db_all_zeros()
    summary = asyncio.run(get_quality_summary(db))
    counts = summary["severity_counts"]
    assert "high" in counts
    assert "medium" in counts
    assert "low" in counts


def test_get_quality_summary_total_matches_issues():
    from src.services.governance.data_quality import get_quality_summary

    db = _db_all_zeros()
    summary = asyncio.run(get_quality_summary(db))
    assert summary["total_issues"] == len(summary["issues"])
