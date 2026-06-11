"""
J7.2: Built-in report templates for common business scenarios.
"""
from __future__ import annotations

from typing import Any, Dict, List

TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "ops_monthly",
        "name": "系统运营月报",
        "description": "涵盖查询量、错误率、活跃用户、性能指标",
        "schedule": {"cron": "0 8 1 * *"},   # 1st of every month at 08:00
        "config": [
            {"data_source": "metrics", "metric": "usage",      "period": "30d"},
            {"data_source": "metrics", "metric": "operations",  "period": "30d"},
            {"data_source": "metrics", "metric": "quality",     "period": "30d"},
        ],
        "sections": ["使用情况", "运营指标", "质量概览"],
    },
    {
        "id": "user_weekly",
        "name": "用户活跃度周报",
        "description": "按日展示活跃用户、查询分布、高频主题",
        "schedule": {"cron": "0 8 * * 1"},   # every Monday at 08:00
        "config": [
            {"data_source": "metrics", "metric": "usage", "period": "7d"},
        ],
        "sections": ["周活跃用户", "热门主题", "增长趋势"],
    },
    {
        "id": "quality_quarterly",
        "name": "知识质量季报",
        "description": "评分分布、低质量答案分析、改进建议",
        "schedule": {"cron": "0 8 1 1,4,7,10 *"},  # quarterly
        "config": [
            {"data_source": "metrics", "metric": "quality", "period": "90d"},
        ],
        "sections": ["质量趋势", "问题分布", "建议行动"],
    },
    {
        "id": "perf_daily",
        "name": "性能日报",
        "description": "每日 QPS 趋势、P95 延迟、错误分布",
        "schedule": {"cron": "0 8 * * *"},  # every day 08:00
        "config": [
            {"data_source": "metrics", "metric": "operations", "period": "7d"},
        ],
        "sections": ["QPS 趋势", "延迟分布", "错误分析"],
    },
    {
        "id": "security_monthly",
        "name": "安全合规月报",
        "description": "等保检查结果、异常登录、权限变更",
        "schedule": {"cron": "0 8 1 * *"},
        "config": [
            {"data_source": "postgres", "table": "audit_logs",
             "dimensions": ["event_type", "action"],
             "measures": ["count(*) AS count"],
             "filters": {"event_type": "error"},
             "order_by": "count", "order_desc": True},
        ],
        "sections": ["合规评分", "异常事件", "权限审计"],
    },
]

TEMPLATE_MAP = {t["id"]: t for t in TEMPLATES}


def get_template(template_id: str) -> Dict[str, Any] | None:
    return TEMPLATE_MAP.get(template_id)


def list_templates() -> List[Dict[str, Any]]:
    return [{k: v for k, v in t.items() if k != "config"} for t in TEMPLATES]
