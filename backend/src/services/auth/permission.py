"""F2.3 — Permission checker: FastAPI dependency + decorator."""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_current_user
from ...db.models import User
from ...db.rbac_models import Permission, Role, RolePermission, UserRole
from ...db.session import get_db


async def _get_user_permissions(user: User, db: AsyncSession) -> set[str]:
    """Return set of 'resource:action' strings for the user."""
    if user.is_admin:
        # Admins retain all permissions without a role assignment
        rows = (await db.execute(select(Permission))).scalars().all()
        return {f"{p.resource}:{p.action}" for p in rows}

    rows = (await db.execute(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == str(user.id))
    )).scalars().all()
    return {f"{p.resource}:{p.action}" for p in rows}


def require_permission(resource: str, action: str):
    """FastAPI dependency that raises 403 if the user lacks resource:action."""
    async def _dep(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        perms = await _get_user_permissions(user, db)
        if f"{resource}:{action}" not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {resource}:{action}",
            )
        return user
    return _dep


async def get_user_roles(user_id: str, db: AsyncSession) -> list[str]:
    """Return list of role names for a user."""
    rows = (await db.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )).scalars().all()
    return list(rows)


async def assign_role(user_id: str, role_name: str, granted_by: str | None,
                      db: AsyncSession) -> None:
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    if not role:
        raise ValueError(f"Role {role_name!r} not found")
    exists = (await db.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
    )).scalar_one_or_none()
    if not exists:
        db.add(UserRole(user_id=user_id, role_id=role.id, granted_by=granted_by))
        await db.commit()


async def revoke_role(user_id: str, role_name: str, db: AsyncSession) -> None:
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    if not role:
        return
    ur = (await db.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id)
    )).scalar_one_or_none()
    if ur:
        await db.delete(ur)
        await db.commit()
