"""
OPC-UA real-time parameter monitoring.

Polls OPC-UA server for industrial process parameters and compares
against Neo4j Constraint nodes. Triggers WebSocket alerts on violations.

Usage (background coroutine):
    asyncio.create_task(monitor_loop())

Requirements:
    pip install asyncua
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

log = logging.getLogger(__name__)

OPCUA_ENDPOINT = os.getenv("OPCUA_ENDPOINT", "opc.tcp://localhost:4840/freeopcua/server/")
OPCUA_POLL_INTERVAL = int(os.getenv("OPCUA_POLL_INTERVAL", "5"))  # seconds

# Maps OPC-UA node ID → (parameter_name, unit, component_part_no)
OPCUA_NODE_MAP: dict[str, tuple[str, str, str]] = {
    "ns=2;i=2": ("液压压力", "PSI", "HYD-MAIN-001"),
    "ns=2;i=3": ("安装力矩", "N·m", "FITTING-A-001"),
    "ns=2;i=4": ("液压温度", "°C", "HYD-MAIN-001"),
}


@dataclass
class ConstraintSpec:
    parameter: str
    min_val: float | None
    max_val: float | None
    unit: str
    section_id: str
    doc_id: str


async def get_constraint_specs(parameter: str, unit: str) -> list[ConstraintSpec]:
    """Fetch constraint specs from Neo4j."""
    from .graph.conflict_detection import check_constraint_compliance  # noqa: F401
    from ..core.database import get_driver

    def _run():
        driver = get_driver()
        with driver.session() as s:
            result = s.run(
                """
                MATCH (c:Constraint)<-[:HAS_CONSTRAINT]-(sec:Section)
                WHERE c.parameter CONTAINS $param AND c.unit = $unit
                RETURN c.min AS min_val, c.max AS max_val,
                       c.value AS spec_val, sec.chunk_id AS section_id,
                       sec.doc_id AS doc_id
                LIMIT 5
                """,
                param=parameter, unit=unit,
            )
            specs = []
            for r in result:
                min_v = float(r["min_val"]) if r["min_val"] is not None else None
                max_v = float(r["max_val"]) if r["max_val"] is not None else None
                if min_v is None and r["spec_val"] is not None:
                    try:
                        v = float(r["spec_val"])
                        min_v, max_v = v * 0.9, v * 1.1
                    except ValueError:
                        pass
                specs.append(ConstraintSpec(
                    parameter=parameter, min_val=min_v, max_val=max_v,
                    unit=unit, section_id=r["section_id"], doc_id=r["doc_id"],
                ))
            return specs

    return await asyncio.to_thread(_run)


def check_violation(value: float, spec: ConstraintSpec) -> str | None:
    """Return violation message or None if compliant."""
    if spec.min_val is not None and value < spec.min_val:
        return (f"{spec.parameter} 当前值 {value} {spec.unit} "
                f"低于最小值 {spec.min_val} {spec.unit} "
                f"（{spec.doc_id} §{spec.section_id}）")
    if spec.max_val is not None and value > spec.max_val:
        return (f"{spec.parameter} 当前值 {value} {spec.unit} "
                f"超出最大值 {spec.max_val} {spec.unit} "
                f"（{spec.doc_id} §{spec.section_id}）")
    return None


async def push_violation_alert(node_id: str, value: float,
                                 message: str) -> None:
    """Push violation alert via Redis pub/sub → WebSocket."""
    try:
        import json
        import redis.asyncio as aioredis
        from ..core.config import settings
        r = aioredis.from_url(settings.REDIS_URL)
        await r.publish("opcua:alerts", json.dumps({
            "node_id": node_id,
            "value": value,
            "message": message,
        }))
        await r.aclose()
    except Exception as exc:
        log.warning("Failed to push OPC-UA alert: %s", exc)


async def poll_once() -> list[dict[str, Any]]:
    """Poll OPC-UA server once and return violations."""
    violations = []
    try:
        from asyncua import Client
        async with Client(url=OPCUA_ENDPOINT) as client:
            for node_id, (param, unit, component) in OPCUA_NODE_MAP.items():
                try:
                    node = client.get_node(node_id)
                    value = float(await node.get_value())
                    specs = await get_constraint_specs(param, unit)
                    for spec in specs:
                        msg = check_violation(value, spec)
                        if msg:
                            violations.append({
                                "node_id": node_id,
                                "parameter": param,
                                "value": value,
                                "unit": unit,
                                "message": msg,
                            })
                            await push_violation_alert(node_id, value, msg)
                except Exception as exc:
                    log.debug("Node %s read failed: %s", node_id, exc)
    except ImportError:
        log.debug("asyncua not installed — OPC-UA monitoring disabled")
    except Exception as exc:
        log.warning("OPC-UA poll failed: %s", exc)
    return violations


async def monitor_loop() -> None:
    """Background coroutine — runs indefinitely until cancelled."""
    log.info("OPC-UA monitor started (endpoint=%s, interval=%ds)",
             OPCUA_ENDPOINT, OPCUA_POLL_INTERVAL)
    while True:
        violations = await poll_once()
        if violations:
            log.warning("OPC-UA violations: %d alerts", len(violations))
        await asyncio.sleep(OPCUA_POLL_INTERVAL)
