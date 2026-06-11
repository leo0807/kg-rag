"""
J3.2: Report query engine — safely executes DSL-driven queries against Postgres/Neo4j/metrics.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── SQL Safety ────────────────────────────────────────────────────────────────

_ALLOWED_TABLES = {
    "audit_logs", "qa_feedback", "users", "documents",
    "local_models", "finetune_jobs", "api_keys", "tenants",
}

_BANNED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE|EXEC|EXECUTE)\b",
    re.IGNORECASE,
)


def _validate_sql(sql: str) -> None:
    if _BANNED_KEYWORDS.search(sql):
        raise ValueError("SQL 包含禁止关键字（仅允许 SELECT）")
    # Extract table names from simple FROM/JOIN clauses
    tables = re.findall(r"(?:FROM|JOIN)\s+(\w+)", sql, re.IGNORECASE)
    for t in tables:
        if t.lower() not in _ALLOWED_TABLES:
            raise ValueError(f"不允许查询表: {t}（仅允许 {_ALLOWED_TABLES}）")


def _safe_identifier(name: str) -> str:
    """Strip anything that isn't alphanumeric or underscore."""
    return re.sub(r"[^\w]", "", name)


# ── Query builders ────────────────────────────────────────────────────────────

class _PostgresQueryBuilder:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.cfg = config

    def build(self) -> str:
        table    = _safe_identifier(self.cfg.get("table", "audit_logs"))
        measures = [_safe_identifier(m) for m in self.cfg.get("measures", ["count(*)"])]
        dims     = [_safe_identifier(d) for d in self.cfg.get("dimensions", [])]
        filters  = self.cfg.get("filters", {})
        order_by = _safe_identifier(self.cfg.get("order_by", "")) if self.cfg.get("order_by") else None
        limit    = min(int(self.cfg.get("limit", 1000)), 5000)

        select_cols = dims + measures
        sql = f"SELECT {', '.join(select_cols)} FROM {table}"

        where_parts: List[str] = []
        for col, val in filters.items():
            safe_col = _safe_identifier(col)
            if isinstance(val, list):
                placeholders = ", ".join(["?"] * len(val))
                where_parts.append(f"{safe_col} IN ({placeholders})")
            else:
                where_parts.append(f"{safe_col} = ?")
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)

        if dims:
            sql += f" GROUP BY {', '.join(dims)}"
        if order_by:
            direction = "DESC" if self.cfg.get("order_desc") else "ASC"
            sql += f" ORDER BY {order_by} {direction}"
        sql += f" LIMIT {limit}"
        return sql


class _MetricsQueryBuilder:
    """Returns metrics from the insights engine instead of raw SQL."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.cfg = config

    async def execute(self, db) -> List[Dict[str, Any]]:
        from .insights_engine import insights_engine
        metric = self.cfg.get("metric", "usage")
        period = self.cfg.get("period", "30d")
        if metric == "usage":
            r = await insights_engine.usage_insights(db, period)
            return r.get("daily_query_trend", [])
        if metric == "quality":
            r = await insights_engine.quality_insights(db, period)
            return r.get("accuracy_trend", [])
        if metric == "operations":
            r = await insights_engine.operations_insights(db, period)
            return r.get("qps_trend", [])
        return []


# ── Engine ────────────────────────────────────────────────────────────────────

class ReportEngine:
    """Executes report DSL configs and returns structured data for visualization."""

    async def query(self, config: Dict[str, Any], db) -> Dict[str, Any]:
        source = config.get("data_source", "postgres")
        try:
            if source == "postgres":
                return await self._query_postgres(config, db)
            if source == "neo4j":
                return await self._query_neo4j(config)
            if source == "metrics":
                builder = _MetricsQueryBuilder(config)
                rows = await builder.execute(db)
                return {"rows": rows, "source": "metrics"}
        except Exception as e:
            logger.warning("ReportEngine.query failed: %s", e)
            return {"rows": [], "error": str(e)}
        return {"rows": [], "error": f"未知数据源: {source}"}

    async def _query_postgres(self, config: Dict[str, Any], db) -> Dict[str, Any]:
        from sqlalchemy import text

        if "raw_sql" in config:
            sql = config["raw_sql"]
            _validate_sql(sql)
        else:
            sql = _PostgresQueryBuilder(config).build()

        result = await db.execute(text(sql))
        cols = list(result.keys())
        rows = [dict(zip(cols, row)) for row in result.fetchall()]
        return {"rows": rows, "columns": cols, "source": "postgres"}

    async def _query_neo4j(self, config: Dict[str, Any]) -> Dict[str, Any]:
        from ...core.database import get_driver
        cypher = config.get("cypher", "MATCH (n) RETURN count(n) AS total LIMIT 1")
        driver = get_driver()
        with driver.session() as session:
            result = session.run(cypher)
            rows = [dict(r) for r in result]
        return {"rows": rows, "source": "neo4j"}

    def recommend_viz(self, rows: List[Dict[str, Any]], config: Dict[str, Any]) -> str:
        """Suggest chart type based on data shape."""
        if not rows:
            return "table"
        cols = list(rows[0].keys())
        numeric_cols = [c for c in cols if isinstance(rows[0][c], (int, float))]
        if "date" in cols or "hour" in cols:
            return "line"
        if len(cols) == 2 and len(numeric_cols) == 1:
            return "bar"
        if len(numeric_cols) == 1 and len(rows) <= 8:
            return "pie"
        if len(numeric_cols) >= 2:
            return "scatter"
        return "table"


report_engine = ReportEngine()
