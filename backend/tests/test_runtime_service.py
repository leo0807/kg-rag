from src.services.ops.runtime_service import summarize_system_pressure


def test_summarize_system_pressure_low_load():
    result = summarize_system_pressure(
        services={
            "neo4j": {"state": "ok", "latency_ms": 42},
            "milvus": {"state": "ok", "latency_ms": 58},
            "elasticsearch": {"state": "ok", "latency_ms": 61},
        },
        runtime={"running": 1, "queued": 0, "failed": 0},
        active_users=2,
        requests_1m=18,
    )

    assert result["level"] == "low"
    assert "平稳" in result["summary"]


def test_summarize_system_pressure_high_load_when_services_degraded():
    result = summarize_system_pressure(
        services={
            "neo4j": {"state": "down", "latency_ms": 1600},
            "milvus": {"state": "ok", "latency_ms": 210},
            "elasticsearch": {"state": "down", "latency_ms": 980},
        },
        runtime={"running": 7, "queued": 6, "failed": 2},
        active_users=14,
        requests_1m=260,
    )

    assert result["level"] == "high"
    assert result["score"] >= 55
    assert any("依赖异常" in factor for factor in result["factors"])
