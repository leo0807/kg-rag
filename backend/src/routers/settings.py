"""
src/routers/settings.py
用户配置和系统配置管理
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from ..db.session import get_db
from ..db.models import User, UserSetting, SystemSetting, AuditLog
from ..auth.deps import get_current_user, get_admin_user
from ..services.runtime.model_settings import DEFAULT_SETTINGS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])

class SettingUpdate(BaseModel):
    key:   str
    value: str


class SettingsBatch(BaseModel):
    settings: dict[str, str]


@router.get("/defaults")
async def get_defaults():
    """获取系统默认配置"""
    return DEFAULT_SETTINGS


@router.get("/system")
async def get_system_settings(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_admin_user),
):
    """获取系统配置（仅管理员）"""
    result = await db.execute(select(SystemSetting))
    rows   = result.scalars().all()
    data   = {r.key: r.value for r in rows}
    # 用默认值填充缺失的配置
    return {**DEFAULT_SETTINGS, **data}


@router.put("/system")
async def update_system_settings(
    req:  SettingsBatch,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_admin_user),
):
    """批量更新系统配置（仅管理员）"""
    for key, value in req.settings.items():
        result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(SystemSetting(key=key, value=value))

    log = AuditLog(
        user_id  = user.id,
        action   = "update_system_settings",
        resource = "system_settings",
        detail   = f"更新了 {len(req.settings)} 个系统配置",
    )
    db.add(log)
    await db.commit()
    return {"status": "OK", "updated": len(req.settings)}


@router.get("/user")
async def get_user_settings(
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """获取当前用户配置（合并系统配置和用户配置）"""
    # 系统配置
    sys_result = await db.execute(select(SystemSetting))
    sys_data   = {r.key: r.value for r in sys_result.scalars().all()}

    # 用户配置
    usr_result = await db.execute(
        select(UserSetting).where(UserSetting.user_id == user.id)
    )
    usr_data = {r.key: r.value for r in usr_result.scalars().all()}

    # 优先级：用户配置 > 系统配置 > 默认配置
    return {**DEFAULT_SETTINGS, **sys_data, **usr_data}


@router.put("/user")
async def update_user_settings(
    req:  SettingsBatch,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """批量更新用户配置"""
    for key, value in req.settings.items():
        if key not in DEFAULT_SETTINGS:
            raise HTTPException(400, f"不支持的配置项: {key}")

        result = await db.execute(
            select(UserSetting).where(
                UserSetting.user_id == user.id,
                UserSetting.key     == key,
            )
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
        else:
            db.add(UserSetting(user_id=user.id, key=key, value=value))

    log = AuditLog(
        user_id  = user.id,
        action   = "update_user_settings",
        resource = "user_settings",
        detail   = f"更新了 {len(req.settings)} 个用户配置",
    )
    db.add(log)
    await db.commit()
    return {"status": "OK", "updated": len(req.settings)}


class AlertTestRequest(BaseModel):
    dingtalk_webhook: str = ""
    wecom_webhook:    str = ""


@router.post("/alert/test")
async def test_alert(
    req:  AlertTestRequest,
    user: User = Depends(get_admin_user),
):
    """向指定 Webhook 发送一条测试告警（仅管理员）"""
    from ..services.alert_service import AlertService
    svc = AlertService.__new__(AlertService)
    svc._init()
    svc._last_sent = {}  # 测试时不受冷却限制

    from ..services.runtime.model_settings import get_runtime_settings_namespace
    runtime = get_runtime_settings_namespace()
    _orig_dt = getattr(runtime, "DINGTALK_WEBHOOK", "")
    _orig_wc = getattr(runtime, "WECOM_WEBHOOK", "")

    sent = []
    if req.dingtalk_webhook:
        await svc._send_dingtalk(req.dingtalk_webhook, "✅ **CPS知识库测试告警**\n\n钉钉推送配置正常。")
        sent.append("dingtalk")
    if req.wecom_webhook:
        await svc._send_wecom(req.wecom_webhook, "✅ **CPS知识库测试告警**\n\n企业微信推送配置正常。")
        sent.append("wecom")

    if not sent:
        raise HTTPException(400, "未提供任何 Webhook URL")
    return {"status": "OK", "sent": sent}


@router.delete("/user/{key}")
async def delete_user_setting(
    key:  str,
    db:   AsyncSession = Depends(get_db),
    user: User         = Depends(get_current_user),
):
    """删除用户配置（恢复到系统默认）"""
    await db.execute(
        delete(UserSetting).where(
            UserSetting.user_id == user.id,
            UserSetting.key     == key,
        )
    )
    await db.commit()
    return {"status": "OK"}
