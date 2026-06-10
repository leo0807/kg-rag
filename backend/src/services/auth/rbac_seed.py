"""F2.2 — Seed built-in roles and permissions on startup."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.rbac_models import Permission, Role, RolePermission

logger = logging.getLogger(__name__)

# Built-in roles: (name, display_name, description)
_ROLES = [
    ("super_admin", "超级管理员", "完整系统权限，不受任何限制"),
    ("admin",       "管理员",    "可管理用户、文档和系统配置"),
    ("editor",      "编辑者",    "可上传、编辑文档和图谱"),
    ("analyst",     "分析师",    "可查询、导出数据，无写权限"),
    ("viewer",      "访客",      "只读访问基本内容"),
    ("guest",       "游客",      "最低权限，仅能浏览公开内容"),
]

# Permission matrix: (resource, action)
_PERMISSIONS = [
    ("document", "read"), ("document", "create"), ("document", "update"), ("document", "delete"),
    ("document", "export"),
    ("graph", "read"), ("graph", "write"),
    ("query", "run"),
    ("user", "read"), ("user", "create"), ("user", "update"), ("user", "delete"),
    ("audit", "read"), ("audit", "export"),
    ("config", "read"), ("config", "write"),
    ("eval", "read"), ("eval", "run"),
]

# role_name → set of (resource, action) it grants
_ROLE_PERMS: dict[str, list[tuple[str, str]]] = {
    "super_admin": _PERMISSIONS,
    "admin":       [p for p in _PERMISSIONS if p[0] != "config" or p[1] == "read"],
    "editor": [
        ("document", "read"), ("document", "create"), ("document", "update"),
        ("graph", "read"), ("graph", "write"), ("query", "run"),
    ],
    "analyst": [
        ("document", "read"), ("document", "export"),
        ("graph", "read"), ("query", "run"),
        ("audit", "read"), ("eval", "read"),
    ],
    "viewer": [
        ("document", "read"), ("graph", "read"), ("query", "run"),
    ],
    "guest": [
        ("document", "read"), ("graph", "read"),
    ],
}


async def seed_rbac(db: AsyncSession) -> None:
    """Idempotent: skips already-existing roles/permissions."""
    # Upsert permissions
    perm_map: dict[tuple[str, str], Permission] = {}
    for resource, action in _PERMISSIONS:
        existing = (await db.execute(
            select(Permission).where(Permission.resource == resource, Permission.action == action)
        )).scalar_one_or_none()
        if not existing:
            existing = Permission(resource=resource, action=action,
                                  description=f"{resource}:{action}")
            db.add(existing)
            await db.flush()
        perm_map[(resource, action)] = existing

    # Upsert roles + their permission assignments
    for name, display_name, description in _ROLES:
        role = (await db.execute(select(Role).where(Role.name == name))).scalar_one_or_none()
        if not role:
            role = Role(name=name, display_name=display_name,
                        description=description, is_system=True)
            db.add(role)
            await db.flush()

        # Grant permissions not yet assigned
        for res, act in _ROLE_PERMS.get(name, []):
            perm = perm_map.get((res, act))
            if not perm:
                continue
            exists = (await db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == perm.id,
                )
            )).scalar_one_or_none()
            if not exists:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))

    await db.commit()
    logger.info("RBAC seed complete")
