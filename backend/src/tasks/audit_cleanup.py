"""
backend/src/tasks/audit_cleanup.py
审计日志自动清理任务
"""
import logging
from datetime import datetime, timedelta
from sqlalchemy import delete
from ..db.session import AsyncSessionLocal
from ..db.models import AuditLog

logger = logging.getLogger(__name__)

async def cleanup_audit_logs(retention_days: int = 365):
    """
    清理超过保留期限的审计日志。
    目前仅执行物理删除，归档至对象存储需配置 S3/OSS 客户端。
    """
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    
    async with AsyncSessionLocal() as db:
        try:
            # 查找待删除的数量（可选，用于日志记录）
            stmt = delete(AuditLog).where(AuditLog.created_at < cutoff)
            result = await db.execute(stmt)
            await db.commit()
            
            count = result.rowcount
            if count > 0:
                logger.info("审计日志清理完成：删除了 %d 条超过 %d 天的记录 (截止日期: %s)", 
                            count, retention_days, cutoff.isoformat())
        except Exception as e:
            logger.error("审计日志清理任务失败: %s", e)
            await db.rollback()
