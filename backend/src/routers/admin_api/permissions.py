"""F2.5 — RBAC admin API: roles, permissions, user-role assignments."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.deps import get_admin_user
from ...db.models import User
from ...db.rbac_models import Permission, Role, RolePermission, UserRole
from ...db.session import get_db
from ...services.auth.permission import assign_role, get_user_roles, revoke_role

router = APIRouter(prefix="/api/admin/rbac", tags=["admin-rbac"])


@router.get("/roles")
async def list_roles(
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    roles = (await db.execute(select(Role))).scalars().all()
    out = []
    for r in roles:
        perm_rows = (await db.execute(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == r.id)
        )).scalars().all()
        out.append({
            "id": r.id, "name": r.name, "display_name": r.display_name,
            "description": r.description, "is_system": r.is_system,
            "permissions": [f"{p.resource}:{p.action}" for p in perm_rows],
        })
    return out


@router.get("/permissions")
async def list_permissions(
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    rows = (await db.execute(select(Permission))).scalars().all()
    return [{"id": p.id, "resource": p.resource, "action": p.action,
             "key": f"{p.resource}:{p.action}"} for p in rows]


@router.get("/users/{user_id}/roles")
async def get_roles_for_user(
    user_id: str,
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    return {"user_id": user_id, "roles": await get_user_roles(user_id, db)}


class RoleAssign(BaseModel):
    role_name: str


@router.post("/users/{user_id}/roles")
async def add_role(
    user_id: str, body: RoleAssign,
    admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    try:
        await assign_role(user_id, body.role_name, str(admin.id), db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.delete("/users/{user_id}/roles/{role_name}")
async def remove_role(
    user_id: str, role_name: str,
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    await revoke_role(user_id, role_name, db)
    return {"ok": True}


@router.get("/users")
async def list_users_with_roles(
    _admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)
):
    users = (await db.execute(select(User))).scalars().all()
    result = []
    for u in users:
        roles = await get_user_roles(str(u.id), db)
        result.append({
            "id": str(u.id), "username": u.username,
            "full_name": getattr(u, "full_name", u.username),
            "is_admin": u.is_admin, "roles": roles,
        })
    return result
