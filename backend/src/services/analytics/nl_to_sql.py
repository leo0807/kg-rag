"""
J4.2: Natural language to SQL conversion with safety checks.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from .report_engine import _validate_sql

logger = logging.getLogger(__name__)

# Simplified schema context for the LLM
_SCHEMA_CONTEXT = """
可用数据表（只读）：
- audit_logs(id, user_id, tenant_id, event_type, action, resource_type, resource_id, timestamp)
  -- 系统操作日志，event_type: 'query'|'error'|'login'|'upload'
- qa_feedback(id, qa_log_id, user_id, rating, comment, created_at)
  -- 用户对答案的评分，rating 1-5
- users(id, username, email, is_active, is_admin, created_at)
  -- 用户表
- documents(id, title, file_type, status, created_at, updated_at)
  -- 知识库文档
- local_models(id, name, backend, is_loaded, parameters_b, created_at)
  -- 本地 AI 模型

规则：只允许 SELECT 语句，LIMIT 不超过 1000。
"""

_VIZ_RULES = """
根据 SQL 结果推荐可视化：
- 有 date/hour/time 列 → line（折线图）
- 两列且一个数值 → bar（柱状图）
- 名称+占比 → pie（饼图）
- 多数值列 → scatter（散点图）
- 其他 → table（表格）
"""


class NLToSQL:
    """Converts natural language questions to SQL queries and executes them."""

    async def query(self, question: str, db: AsyncSession) -> Dict[str, Any]:
        sql = await self._generate_sql(question)
        safe_sql, err = self._check_sql(sql)
        if err:
            return {"error": err, "sql": sql, "data": [], "viz_type": "table"}

        data, columns, exec_err = await self._execute(safe_sql, db)
        viz_type = self._recommend_viz(data, columns)
        viz_config = self._build_viz_config(viz_type, columns)

        return {
            "question": question,
            "sql": safe_sql,
            "data": data,
            "columns": columns,
            "viz_type": viz_type,
            "viz_config": viz_config,
            "error": exec_err,
        }

    async def _generate_sql(self, question: str) -> str:
        """Use LLM to convert NL to SQL."""
        try:
            from ...services.ai.llm_service import LLMService
            llm = LLMService()
            prompt = (
                f"{_SCHEMA_CONTEXT}\n\n"
                f"请将以下问题转换为 SQL：\n{question}\n\n"
                "只返回 SQL 语句，不要解释，不要 Markdown 代码块。"
            )
            sql = await llm.generate(prompt, max_tokens=200)
            # Strip markdown if present
            sql = re.sub(r"```\w*\n?", "", sql).strip()
            return sql
        except Exception as e:
            logger.warning("LLM SQL generation failed: %s", e)
            return self._heuristic_sql(question)

    def _heuristic_sql(self, question: str) -> str:
        """Fallback: simple keyword-based SQL generation."""
        q_lower = question.lower()
        if "用户" in q_lower or "user" in q_lower:
            return "SELECT username, created_at FROM users WHERE is_active=true ORDER BY created_at DESC LIMIT 20"
        if "错误" in q_lower or "error" in q_lower:
            return "SELECT action, COUNT(*) AS count FROM audit_logs WHERE event_type='error' GROUP BY action ORDER BY count DESC LIMIT 10"
        if "文档" in q_lower or "document" in q_lower:
            return "SELECT title, file_type, status, created_at FROM documents ORDER BY created_at DESC LIMIT 20"
        if "评分" in q_lower or "rating" in q_lower or "反馈" in q_lower:
            return "SELECT rating, COUNT(*) AS count FROM qa_feedback GROUP BY rating ORDER BY rating"
        return "SELECT event_type, COUNT(*) AS count FROM audit_logs GROUP BY event_type ORDER BY count DESC"

    def _check_sql(self, sql: str) -> tuple[str, str | None]:
        sql = sql.strip().rstrip(";")
        if not sql.upper().startswith("SELECT"):
            return sql, "只允许 SELECT 语句"
        try:
            _validate_sql(sql)
        except ValueError as e:
            return sql, str(e)
        # Enforce LIMIT
        if "LIMIT" not in sql.upper():
            sql += " LIMIT 200"
        return sql, None

    async def _execute(
        self, sql: str, db: AsyncSession
    ) -> tuple[List[Dict[str, Any]], List[str], str | None]:
        try:
            from sqlalchemy import text
            result = await db.execute(text(sql))
            cols = list(result.keys())
            rows = [dict(zip(cols, row)) for row in result.fetchall()]
            return rows, cols, None
        except Exception as e:
            logger.warning("SQL execution failed: %s", e)
            return [], [], f"SQL 执行失败: {e}"

    def _recommend_viz(self, data: List[Dict[str, Any]], columns: List[str]) -> str:
        if not data or not columns:
            return "table"
        numeric = [c for c in columns if isinstance(data[0].get(c), (int, float))]
        if any(c in columns for c in ("date", "hour", "week", "month", "timestamp")):
            return "line"
        if len(columns) == 2 and len(numeric) == 1 and len(data) <= 10:
            return "pie"
        if len(numeric) >= 1 and len(columns) <= 3:
            return "bar"
        if len(numeric) >= 2:
            return "scatter"
        return "table"

    def _build_viz_config(self, viz_type: str, columns: List[str]) -> Dict[str, Any]:
        numeric = []  # will be inferred from data at render time
        date_col = next((c for c in columns if c in ("date", "hour", "week", "month")), columns[0] if columns else "x")
        return {"x": date_col, "y": [c for c in columns if c != date_col][:3]}


nl_to_sql = NLToSQL()
