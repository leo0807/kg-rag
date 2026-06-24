"""
Unit tests for src/services/infra/health.py
Tests ServiceStatus, ServiceState, and ServiceHealthMonitor (without live connections).
"""
import time
import pytest

from src.services.infra.health import (
    ServiceState,
    ServiceStatus,
    ServiceHealthMonitor,
    PING_INTERVAL_SECONDS,
)


# ── ServiceState ────────────────────────────────────────────────────────────

def test_service_state_values():
    assert ServiceState.OK == "ok"
    assert ServiceState.DOWN == "down"
    assert ServiceState.UNKNOWN == "unknown"


def test_service_state_is_string():
    # ServiceState inherits from str
    assert isinstance(ServiceState.OK, str)


# ── ServiceStatus ────────────────────────────────────────────────────────────

def test_service_status_defaults():
    s = ServiceStatus(name="test")
    assert s.name == "test"
    assert s.state == ServiceState.UNKNOWN
    assert s.error == ""
    assert s.latency_ms == 0.0
    assert s.last_check == 0.0


def test_service_status_is_ok_true():
    s = ServiceStatus(name="neo4j", state=ServiceState.OK)
    assert s.is_ok is True


def test_service_status_is_ok_false_down():
    s = ServiceStatus(name="neo4j", state=ServiceState.DOWN)
    assert s.is_ok is False


def test_service_status_is_ok_false_unknown():
    s = ServiceStatus(name="neo4j")  # default UNKNOWN
    assert s.is_ok is False


def test_service_status_to_dict_structure():
    s = ServiceStatus(
        name="milvus",
        state=ServiceState.OK,
        error="",
        latency_ms=12.345,
        last_check=1700000000.0,
    )
    d = s.to_dict()
    assert d["state"] == ServiceState.OK
    assert d["error"] == ""
    assert d["latency_ms"] == 12.35   # rounded to 2 decimal places
    assert d["last_check"] == 1700000000


def test_service_status_to_dict_no_last_check():
    s = ServiceStatus(name="es")  # last_check = 0.0
    d = s.to_dict()
    assert d["last_check"] is None


# ── ServiceHealthMonitor ─────────────────────────────────────────────────────

def test_monitor_init():
    m = ServiceHealthMonitor()
    assert isinstance(m.neo4j, ServiceStatus)
    assert isinstance(m.milvus, ServiceStatus)
    assert isinstance(m.elasticsearch, ServiceStatus)
    assert m._task is None


def test_monitor_to_dict_keys():
    m = ServiceHealthMonitor()
    d = m.to_dict()
    assert set(d.keys()) == {"neo4j", "milvus", "elasticsearch"}


def test_monitor_to_dict_contains_status_dicts():
    m = ServiceHealthMonitor()
    d = m.to_dict()
    for key in ("neo4j", "milvus", "elasticsearch"):
        inner = d[key]
        assert "state" in inner
        assert "error" in inner
        assert "latency_ms" in inner


def test_ping_neo4j_down_on_import_error():
    """ping_neo4j catches ImportError from missing driver and marks DOWN."""
    m = ServiceHealthMonitor()
    # The test env has no Neo4j driver configured; ping should return False
    result = m.ping_neo4j()
    assert result is False
    assert m.neo4j.state == ServiceState.DOWN
    assert m.neo4j.latency_ms >= 0.0
    assert m.neo4j.last_check > 0.0


def test_ping_milvus_returns_bool():
    """ping_milvus returns a bool regardless of whether Milvus is reachable."""
    m = ServiceHealthMonitor()
    result = m.ping_milvus()
    assert isinstance(result, bool)
    assert m.milvus.latency_ms >= 0.0
    assert m.milvus.last_check > 0.0


def test_ping_es_down():
    m = ServiceHealthMonitor()
    result = m.ping_es()
    assert result is False
    assert m.elasticsearch.state == ServiceState.DOWN


def test_check_all_returns_dict():
    m = ServiceHealthMonitor()
    results = m.check_all()
    assert isinstance(results, dict)
    assert set(results.keys()) == {"neo4j", "milvus", "elasticsearch"}
    for v in results.values():
        assert isinstance(v, bool)


def test_stop_background_task_noop_when_none():
    """stop_background_task should not raise if _task is None."""
    m = ServiceHealthMonitor()
    m.stop_background_task()  # Should not raise


def test_ping_interval_constant():
    assert PING_INTERVAL_SECONDS == 30
