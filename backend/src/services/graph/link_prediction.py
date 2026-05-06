"""
图谱补全预测 — 基于公共邻居的链路预测，结果缓存至 Redis。

仅对实体节点（Tool / Material / Process / Constraint）做预测；
跳过已存在关系的节点对。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neo4j import Driver

logger = logging.getLogger(__name__)

ENTITY_LABELS = ("Tool", "Material", "Process", "Constraint")
REDIS_KEY = "graph:predictions"
REDIS_TTL = 60 * 60 * 24 * 7  # 7 days


# ── Neo4j 数据拉取 ────────────────────────────────────────────────────────────

def _fetch_graph(driver: "Driver") -> tuple[list[dict], list[tuple[str, str]]]:
    """返回 (nodes, edges)，nodes 只含实体节点。"""
    nodes: list[dict] = []
    edges: list[tuple[str, str]] = []

    labels_str = "|".join(ENTITY_LABELS)
    with driver.session() as session:
        result = session.run(
            f"MATCH (n:{labels_str}) RETURN elementId(n) AS id, labels(n)[0] AS label, "
            "coalesce(n.name, n.id) AS name LIMIT 2000"
        )
        for row in result:
            nodes.append({"id": row["id"], "label": row["label"], "name": row["name"]})

        if not nodes:
            return nodes, edges

        node_ids = [n["id"] for n in nodes]
        result = session.run(
            f"MATCH (a:{labels_str})-[r]-(b:{labels_str}) "
            "WHERE elementId(a) < elementId(b) "
            "RETURN elementId(a) AS a, elementId(b) AS b LIMIT 10000"
        )
        seen: set[tuple[str, str]] = set()
        for row in result:
            pair = (row["a"], row["b"])
            if pair not in seen:
                seen.add(pair)
                edges.append(pair)
        _ = node_ids  # fetched for context
    return nodes, edges


# ── 预测核心 ─────────────────────────────────────────────────────────────────

def _adamic_adar(
    adj: dict[str, set[str]],
    u: str,
    v: str,
) -> float:
    common = adj[u] & adj[v]
    score = 0.0
    for w in common:
        deg = len(adj[w])
        if deg > 1:
            import math
            score += 1.0 / math.log(deg)
    return score


def predict_links(
    driver: "Driver",
    top_k: int = 50,
    min_score: float = 0.01,
) -> list[dict]:
    """运行链路预测，返回 top-k 候选关系列表。"""
    nodes, edges = _fetch_graph(driver)
    if len(nodes) < 4:
        logger.info("实体节点不足，跳过链路预测")
        return []

    node_map = {n["id"]: n for n in nodes}
    adj: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    existing: set[tuple[str, str]] = set()

    for a, b in edges:
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)
            existing.add((min(a, b), max(a, b)))

    node_ids = list(adj.keys())
    candidates: list[tuple[float, str, str]] = []

    # O(N^2) 但 N ≤ 2000，且实际连接密度较低时大部分提前跳过
    for i, u in enumerate(node_ids):
        for v in node_ids[i + 1:]:
            pair = (min(u, v), max(u, v))
            if pair in existing:
                continue
            score = _adamic_adar(adj, u, v)
            if score >= min_score:
                candidates.append((score, u, v))

    candidates.sort(key=lambda x: -x[0])
    results = []
    for score, u, v in candidates[:top_k]:
        nu = node_map.get(u, {})
        nv = node_map.get(v, {})
        results.append({
            "source_id":    u,
            "target_id":    v,
            "source_label": nu.get("label", ""),
            "target_label": nv.get("label", ""),
            "source_name":  nu.get("name", u),
            "target_name":  nv.get("name", v),
            "score":        round(score, 4),
        })
    logger.info("链路预测完成，候选 %d 条", len(results))
    return results


# ── Redis 读写 ────────────────────────────────────────────────────────────────

def run_and_cache_predictions(driver: "Driver", top_k: int = 50) -> list[dict]:
    results = predict_links(driver, top_k=top_k)
    payload = {
        "predictions": results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
    }
    try:
        from ..infra.cache import get_redis
        r = get_redis()
        r.setex(REDIS_KEY, REDIS_TTL, json.dumps(payload))
    except Exception as e:
        logger.warning("Redis 写入链路预测失败: %s", e)
    return results


def get_cached_predictions() -> dict:
    try:
        from ..infra.cache import get_redis
        r = get_redis()
        raw = r.get(REDIS_KEY)
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning("Redis 读取链路预测失败: %s", e)
    return {"predictions": [], "generated_at": None, "count": 0}
