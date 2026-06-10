"""F5.1 — Data quality checks for documents and graph nodes."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def check_document_quality(db: AsyncSession) -> list[dict]:
    """Returns list of quality issues found in the documents table."""
    issues = []
    try:
        # Documents with no content
        result = await db.execute(
            text("SELECT COUNT(*) FROM documents WHERE content IS NULL OR TRIM(content) = ''")
        )
        empty_count = result.scalar() or 0
        if empty_count > 0:
            issues.append({"type": "empty_content", "severity": "high",
                           "count": empty_count, "message": f"{empty_count} 个文档内容为空"})

        # Documents with no title
        result = await db.execute(
            text("SELECT COUNT(*) FROM documents WHERE title IS NULL OR TRIM(title) = ''")
        )
        no_title = result.scalar() or 0
        if no_title > 0:
            issues.append({"type": "missing_title", "severity": "medium",
                           "count": no_title, "message": f"{no_title} 个文档缺少标题"})

        # Duplicate filenames
        result = await db.execute(text(
            "SELECT filename, COUNT(*) c FROM documents "
            "WHERE filename IS NOT NULL GROUP BY filename HAVING COUNT(*) > 1"
        ))
        dups = result.fetchall()
        if dups:
            issues.append({"type": "duplicate_filename", "severity": "low",
                           "count": len(dups),
                           "message": f"{len(dups)} 个重复文件名"})
    except Exception as e:
        logger.warning("Document quality check error: %s", e)

    return issues


async def get_quality_summary(db: AsyncSession) -> dict:
    stats: dict = {"checked_at": datetime.now(timezone.utc).isoformat(), "issues": []}
    stats["issues"] = await check_document_quality(db)
    stats["total_issues"] = len(stats["issues"])
    stats["severity_counts"] = {
        "high":   sum(1 for i in stats["issues"] if i["severity"] == "high"),
        "medium": sum(1 for i in stats["issues"] if i["severity"] == "medium"),
        "low":    sum(1 for i in stats["issues"] if i["severity"] == "low"),
    }
    return stats
