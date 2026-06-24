"""
Unit tests for src/services/governance/compliance_report.py
Tests anomaly threshold constants and the detect_anomalies / generate_report logic
using mocked AsyncSession (asyncio.run, no pytest-asyncio).
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.governance.compliance_report import (
    _ANOMALY_THRESHOLDS,
    detect_anomalies,
    generate_report,
)


# ── Constants ────────────────────────────────────────────────────────────────

def test_anomaly_thresholds_keys():
    assert "failed_login_per_user" in _ANOMALY_THRESHOLDS
    assert "bulk_delete_per_hour" in _ANOMALY_THRESHOLDS
    assert "export_per_hour" in _ANOMALY_THRESHOLDS


def test_anomaly_thresholds_positive():
    for v in _ANOMALY_THRESHOLDS.values():
        assert isinstance(v, int) and v > 0


# ── detect_anomalies ─────────────────────────────────────────────────────────

def _db_no_anomalies():
    """DB mock that returns zero counts for all anomaly queries."""
    db = AsyncMock()
    result = MagicMock()
    result.fetchall.return_value = []  # no brute-force users
    result.scalar.return_value = 0      # delete/export counts
    db.execute.return_value = result
    return db


def test_detect_anomalies_none_when_all_zero():
    db = _db_no_anomalies()
    anomalies = asyncio.run(detect_anomalies(db))
    assert anomalies == []


def test_detect_anomalies_brute_force():
    """When a user has > threshold failed logins, anomaly should be returned."""
    db = AsyncMock()
    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # Return one row: user_name="hacker", count=10
            result.fetchall.return_value = [("hacker", 10)]
        elif call_count == 2:
            result.scalar.return_value = 0  # bulk delete
        else:
            result.scalar.return_value = 0  # export
        return result

    db.execute.side_effect = side_effect
    anomalies = asyncio.run(detect_anomalies(db))
    assert any(a["type"] == "brute_force" for a in anomalies)
    assert any("hacker" in a["message"] for a in anomalies)


def test_detect_anomalies_bulk_delete():
    db = AsyncMock()
    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.fetchall.return_value = []  # no brute force
        elif call_count == 2:
            result.scalar.return_value = 99  # bulk deletes > threshold
        else:
            result.scalar.return_value = 0
        return result

    db.execute.side_effect = side_effect
    anomalies = asyncio.run(detect_anomalies(db))
    assert any(a["type"] == "bulk_delete" for a in anomalies)
    assert any(a["severity"] == "medium" for a in anomalies)


def test_detect_anomalies_high_export():
    db = AsyncMock()
    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.fetchall.return_value = []
        elif call_count == 2:
            result.scalar.return_value = 0
        else:
            result.scalar.return_value = 999  # exports > threshold
        return result

    db.execute.side_effect = side_effect
    anomalies = asyncio.run(detect_anomalies(db))
    assert any(a["type"] == "high_export" for a in anomalies)
    assert any(a["severity"] == "low" for a in anomalies)


def test_detect_anomalies_db_error_returns_empty():
    db = AsyncMock()
    db.execute.side_effect = Exception("DB unavailable")
    anomalies = asyncio.run(detect_anomalies(db))
    assert anomalies == []


# ── generate_report ───────────────────────────────────────────────────────────

def test_generate_report_structure():
    """generate_report returns expected keys with mocked DB."""
    db = AsyncMock()
    # scalars() for AuditEvent query
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock

    # For anomaly sub-calls return zero
    anomaly_result = MagicMock()
    anomaly_result.fetchall.return_value = []
    anomaly_result.scalar.return_value = 0

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return execute_result
        return anomaly_result

    db.execute.side_effect = side_effect

    report = asyncio.run(generate_report(db, days=7))
    assert "report_at" in report
    assert "period_days" in report
    assert "total_events" in report
    assert "total_failures" in report
    assert "failure_rate" in report
    assert "anomalies" in report


def test_generate_report_failure_rate_zero_when_no_events():
    db = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    execute_result = MagicMock()
    execute_result.scalars.return_value = scalars_mock
    anomaly_result = MagicMock()
    anomaly_result.fetchall.return_value = []
    anomaly_result.scalar.return_value = 0

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return execute_result
        return anomaly_result

    db.execute.side_effect = side_effect
    report = asyncio.run(generate_report(db, days=30))
    assert report["failure_rate"] == 0.0
    assert report["total_events"] == 0
