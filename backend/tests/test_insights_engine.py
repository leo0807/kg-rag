"""
Unit tests for src/services/analytics/insights_engine.py
Tests helper functions and InsightsEngine methods using mocked DB.
asyncio.run() used (no pytest-asyncio).
"""
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.services.analytics.insights_engine import (
    InsightsEngine,
    PERIOD_DAYS,
    _days_ago,
    _safe,
    insights_engine,
)


# ── Module-level helpers ──────────────────────────────────────────────────────

def test_period_days_keys():
    assert "7d" in PERIOD_DAYS
    assert "30d" in PERIOD_DAYS
    assert "90d" in PERIOD_DAYS
    assert "1y" in PERIOD_DAYS


def test_days_ago_type():
    result = _days_ago(7)
    assert isinstance(result, datetime)
    assert result.tzinfo == timezone.utc


def test_days_ago_approximate():
    now = datetime.now(tz=timezone.utc)
    result = _days_ago(30)
    diff = (now - result).total_seconds() / 86400
    assert 29.9 <= diff <= 30.1


def test_safe_returns_value():
    async def good():
        return 42

    result = asyncio.run(_safe(good()))
    assert result == 42


def test_safe_returns_default_on_exception():
    async def bad():
        raise RuntimeError("oops")

    result = asyncio.run(_safe(bad(), default="fallback"))
    assert result == "fallback"


def test_safe_returns_none_default():
    async def bad():
        raise ValueError

    result = asyncio.run(_safe(bad()))
    assert result is None


# ── InsightsEngine — private helpers ─────────────────────────────────────────

def _empty_db():
    db = AsyncMock()
    row = MagicMock()
    row.total = 0
    row.users = 1
    row.date = "2026-01-01"
    row.queries = 0
    row.errors = 0
    row.topic = "test"
    row.count = 0
    row.avg_score = 0.0
    row.rating = 5
    row.doc_id = "doc1"
    row.hour = "2026-01-01 00:00:00"
    row.action = "query"
    result = MagicMock()
    result.scalar.return_value = 0
    result.fetchone.return_value = row
    result.fetchall.return_value = []
    db.execute.return_value = result
    return db


def test_count_active_users_returns_int():
    engine = InsightsEngine()
    db = _empty_db()
    start = _days_ago(30)
    result = asyncio.run(engine._count_active_users(db, start, None))
    assert isinstance(result, int)


def test_query_trend_returns_list():
    engine = InsightsEngine()
    db = _empty_db()
    result = asyncio.run(engine._query_trend(db, _days_ago(7), None))
    assert isinstance(result, list)


def test_top_questions_returns_list():
    engine = InsightsEngine()
    db = _empty_db()
    result = asyncio.run(engine._top_questions(db, _days_ago(30), None))
    assert isinstance(result, list)


def test_engagement_metrics_returns_dict():
    engine = InsightsEngine()
    db = _empty_db()
    result = asyncio.run(engine._engagement_metrics(db, _days_ago(30), None))
    assert isinstance(result, dict)
    assert "avg_queries_per_user" in result
    assert "total_queries" in result


# ── InsightsEngine — high-level methods ──────────────────────────────────────

def test_usage_insights_structure():
    engine = InsightsEngine()
    db = _empty_db()
    result = asyncio.run(engine.usage_insights(db, period="7d"))
    assert "active_users" in result
    assert "daily_query_trend" in result
    assert "top_topics" in result
    assert "user_engagement" in result
    assert "growth_rate" in result


def test_quality_insights_structure():
    engine = InsightsEngine()
    db = _empty_db()
    result = asyncio.run(engine.quality_insights(db, period="30d"))
    assert "accuracy_trend" in result
    assert "feedback_distribution" in result
    assert "problematic_areas" in result


def test_knowledge_insights_structure():
    engine = InsightsEngine()
    db = _empty_db()
    result = asyncio.run(engine.knowledge_insights(db, period="30d"))
    assert "hot_documents" in result
    assert "topic_distribution" in result


def test_operations_insights_structure():
    engine = InsightsEngine()
    db = _empty_db()
    result = asyncio.run(engine.operations_insights(db, period="7d"))
    assert "qps_trend" in result
    assert "error_patterns" in result


def test_module_singleton():
    assert isinstance(insights_engine, InsightsEngine)
