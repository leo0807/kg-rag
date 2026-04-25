from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...db.models import SystemSetting, UserSetting

DEFAULT_SETTINGS: dict[str, str] = {
    "embedding_mode": "local",
    "embedding_provider": "",
    "embedding_model": "models/bge-m3",
    "embedding_api_url": "",
    "embedding_api_key": "",
    "reranker_mode": "local",
    "reranker_provider": "",
    "reranker_model": "models/bge-reranker-v2-m3",
    "reranker_api_url": "",
    "reranker_api_key": "",
    "reranker_enabled": "true",
    "llm_mode": "api",
    "llm_provider": "",
    "llm_api_url": "http://localhost:11434/v1",
    "llm_api_key": "ollama",
    "llm_api_secret": "",
    "llm_model": "qwen2.5:7b",
    "vision_mode": "api",
    "qwen_vl_model": "qwen-vl-max",
    "vlm_model": "Qwen/Qwen2.5-VL-32B-Instruct",
    "query_top_k": "5",
    "query_strategy": "parallel",
}

_RUNTIME_SETTING_MAP: dict[str, str] = {
    "embedding_mode": "EMBEDDING_MODE",
    "embedding_provider": "EMBEDDING_PROVIDER",
    "embedding_model": "EMBEDDING_MODEL",
    "embedding_api_url": "EMBEDDING_API_URL",
    "embedding_api_key": "EMBEDDING_API_KEY",
    "reranker_mode": "RERANKER_MODE",
    "reranker_provider": "RERANKER_PROVIDER",
    "reranker_model": "RERANKER_MODEL",
    "reranker_api_url": "RERANKER_API_URL",
    "reranker_api_key": "RERANKER_API_KEY",
    "reranker_enabled": "RERANKER_ENABLED",
    "llm_mode": "LLM_MODE",
    "llm_provider": "LLM_PROVIDER",
    "llm_api_url": "LLM_API_URL",
    "llm_api_key": "LLM_API_KEY",
    "llm_api_secret": "LLM_API_SECRET",
    "llm_model": "LLM_MODEL",
    "vision_mode": "VISION_MODE",
    "qwen_vl_model": "QWEN_VL_MODEL",
    "vlm_model": "VLM_MODEL",
}

_BOOL_RUNTIME_KEYS = {"RERANKER_ENABLED"}
_INT_RUNTIME_KEYS = {"QUERY_TOP_K"}
_RUNTIME_OVERRIDES: ContextVar[dict[str, Any]] = ContextVar(
    "runtime_model_overrides",
    default={},
)


def _coerce_runtime_value(key: str, value: str) -> Any:
    if key in _BOOL_RUNTIME_KEYS:
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if key in _INT_RUNTIME_KEYS:
        try:
            return int(str(value).strip())
        except ValueError:
            return value
    return value


def build_runtime_overrides(user_settings: Mapping[str, str] | None) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for user_key, runtime_key in _RUNTIME_SETTING_MAP.items():
        if not user_settings or user_key not in user_settings:
            continue
        overrides[runtime_key] = _coerce_runtime_value(runtime_key, user_settings[user_key])
    return overrides


def get_runtime_overrides() -> dict[str, Any]:
    return dict(_RUNTIME_OVERRIDES.get())


def get_runtime_setting(name: str, default: Any = None) -> Any:
    return get_runtime_overrides().get(name, default)


def get_runtime_settings_namespace() -> SimpleNamespace:
    merged = settings.model_dump()
    merged.update(get_runtime_overrides())
    return SimpleNamespace(**merged)


@contextmanager
def use_runtime_settings(user_settings: Mapping[str, str] | None):
    token = _RUNTIME_OVERRIDES.set(build_runtime_overrides(user_settings))
    try:
        yield
    finally:
        _RUNTIME_OVERRIDES.reset(token)


async def load_effective_settings(
    db: AsyncSession | None,
    user_id: str | None = None,
) -> dict[str, str]:
    if db is None:
        return dict(DEFAULT_SETTINGS)

    keys = list(DEFAULT_SETTINGS.keys())
    sys_result = await db.execute(
        select(SystemSetting).where(SystemSetting.key.in_(keys))
    )
    sys_data = {row.key: row.value for row in sys_result.scalars().all()}

    usr_data: dict[str, str] = {}
    if user_id:
        usr_result = await db.execute(
            select(UserSetting).where(
                UserSetting.user_id == user_id,
                UserSetting.key.in_(keys),
            )
        )
        usr_data = {row.key: row.value for row in usr_result.scalars().all()}

    return {**DEFAULT_SETTINGS, **sys_data, **usr_data}
