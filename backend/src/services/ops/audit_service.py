from __future__ import annotations

from ...db.models import AuditLog, User


async def append_audit_log(
    db,
    *,
    user: User,
    action: str,
    resource: str,
    detail: str,
) -> None:
    """记录统一运营入口产生的审计日志。"""
    db.add(
        AuditLog(
            user_id=user.id,
            action=action,
            resource=resource,
            detail=detail,
        ),
    )
    await db.commit()
