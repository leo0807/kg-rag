from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any, Iterable
import os

from dotenv import dotenv_values
from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = Path(__file__).parent.parent.parent.parent
ENV_FILE_PATH = _ROOT / ".env"
_SETTINGS_LOCK = RLock()

RELOADABLE_FIELDS = frozenset(
    {
        "LOG_LEVEL",
        "QUERY_CACHE_TTL",
        "SEMANTIC_CACHE_LOOKUP_TIMEOUT",
        "CLARIFICATION_ENABLED",
        "CLARIFICATION_MIN_LENGTH",
        "CLARIFICATION_LLM_CHECK",
        "RETRIEVER_TOP_K",
        "RERANKER_ENABLED",
        "RERANKER_TOP_K",
        "RERANKER_CANDIDATE_K",
        "LLM_TIMEOUT",
        "LLM_MAX_TOKENS",
        "LLM_RETRY_MAX_ATTEMPTS",
        "LLM_RETRY_INITIAL_BACKOFF_SECONDS",
        "LLM_CIRCUIT_BREAKER_THRESHOLD",
        "LLM_CIRCUIT_BREAKER_RESET_SECONDS",
        "MAX_REQUEST_BODY_BYTES",
        "MAX_UPLOAD_FILE_BYTES",
        "SHUTDOWN_GRACE_PERIOD_SECONDS",
        "ALERT_COOLDOWN_MINUTES",
        "EMBEDDING_DEVICE",
        "REMOTE_EMBEDDING_BATCH_SIZE",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        extra="ignore",
    )

    APP_ENV:   str  = "development"
    LOG_LEVEL: str  = "INFO"
    DEBUG:     bool = True

    NEO4J_URI:      str = "bolt://localhost:7687"
    NEO4J_USER:     str = "neo4j"
    NEO4J_PASSWORD: str = "aviation123"

    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    REDIS_URL:       str = "redis://localhost:6379/0"
    QUERY_CACHE_TTL: int = 3600
    SEMANTIC_CACHE_LOOKUP_TIMEOUT: float = 1.0
    CLARIFICATION_ENABLED: bool = True
    CLARIFICATION_MIN_LENGTH: int = 8
    CLARIFICATION_LLM_CHECK: bool = False

    DASHSCOPE_API_KEY: str = ""
    OPENAI_API_KEY:    str = ""

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL:    str = "qwen2.5:7b"
    RETRIEVER_TOP_K: int = 5

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST:       str = "http://localhost:3001"

    EMBEDDING_MODE:     str = "local"
    EMBEDDING_PROVIDER: str = ""            # qwen / ""(通用兼容)
    EMBEDDING_MODEL:    str = "models/bge-m3"
    EMBEDDING_API_URL:  str = ""
    EMBEDDING_API_KEY:  str = ""

    # 通义文本向量专用配置
    EMBEDDING_QWEN_MODEL: str = "text-embedding-v3"
    EMBEDDING_QWEN_DIM:   int = 1024

    REMOTE_EMBEDDING_BATCH_SIZE: int = 25   # 远程 Embedding API 单批最大条数（F125）
    EMBEDDING_DEVICE: str = "auto"          # auto / cpu / cuda / mps（F126）

    RERANKER_MODE:        str  = "local"
    RERANKER_MODEL:       str  = "models/bge-reranker-v2-m3"
    RERANKER_API_URL:     str  = ""
    RERANKER_API_KEY:     str  = ""
    RERANKER_ENABLED:     bool = True
    RERANKER_TOP_K:       int  = 5
    RERANKER_CANDIDATE_K: int  = 20   # 初始召回倍数（top_k * candidate_k 上取整）

    LLM_MODE:     str = "api"
    LLM_PROVIDER: str = ""            # qwen / deepseek / ernie / anthropic / ""(通用兼容)
    LLM_API_URL:  str = "http://localhost:11434/v1"
    LLM_API_KEY:  str = "ollama"
    LLM_MODEL:    str = "qwen2.5:7b"
    LLM_TIMEOUT:  int = 120
    LLM_MAX_TOKENS: int = 800
    LLM_RETRY_MAX_ATTEMPTS: int = 3
    LLM_RETRY_INITIAL_BACKOFF_SECONDS: float = 1.0
    LLM_CIRCUIT_BREAKER_THRESHOLD: int = 5
    LLM_CIRCUIT_BREAKER_RESET_SECONDS: float = 30.0

    # SSE streaming rate (chars/second); 0 = unlimited
    SSE_CHARS_PER_SECOND: int = 0

    # Provider 故障转移
    LLM_FAILOVER_ENABLED:    bool = False
    LLM_FALLBACK_1_URL:      str  = ""
    LLM_FALLBACK_1_KEY:      str  = ""
    LLM_FALLBACK_1_MODEL:    str  = ""
    LLM_FALLBACK_2_URL:      str  = ""
    LLM_FALLBACK_2_KEY:      str  = ""
    LLM_FALLBACK_2_MODEL:    str  = ""

    # 各提供方专用模型名（空则使用默认值）
    LLM_QWEN_MODEL:     str = "qwen-plus"
    LLM_DEEPSEEK_MODEL: str = "deepseek-chat"
    LLM_ERNIE_MODEL:    str = "ernie-4.5-8k"

    # 各提供方 API Key
    DEEPSEEK_API_KEY: str = ""

    # 本地模式专用模型名（via Ollama）
    LOCAL_LLM_QWEN_MODEL:     str = "qwen2.5:7b"
    LOCAL_LLM_DEEPSEEK_MODEL: str = "deepseek-r1:7b"

    DATABASE_URL: str = "postgresql+asyncpg://aviation:aviation123@localhost:5432/aviation"

    JWT_SECRET:       str = "aviation-jwt-secret-change-in-production"
    JWT_EXPIRE_HOURS: int = 24

    FRONTEND_URL: str = "http://localhost:3000"
    ES_URL:       str = "http://localhost:9200"
    VLM_MODEL:    str = "Qwen/Qwen2.5-VL-32B-Instruct"
    APP_VERSION:  str = "1.3.0"

    # 安全限制
    MAX_REQUEST_BODY_BYTES: int = 50 * 1024 * 1024   # 50 MB  — L1 全局兜底
    MAX_UPLOAD_FILE_BYTES:  int = 100 * 1024 * 1024  # 100 MB — L2 上传端点
    SHUTDOWN_GRACE_PERIOD_SECONDS: float = 30.0

    # MinIO / 对象存储
    STORAGE_ENDPOINT:   str = "http://localhost:9000"
    STORAGE_ACCESS_KEY: str = "minioadmin"
    STORAGE_SECRET_KEY: str = "minioadmin"
    STORAGE_REGION:     str = "us-east-1"
    STORAGE_PUBLIC_URL: str = "http://localhost:9000"

    # Vision 多模态服务
    VISION_MODE:           str = "api"      # "api" | "local"
    QWEN_VL_MODEL:         str = "qwen-vl-max"
    ERNIE_API_KEY:         str = ""
    ERNIE_SECRET_KEY:      str = ""
    HUNYUAN_API_KEY:       str = ""
    LOCAL_VLM_PATH:        str = "models/qwen2-vl"
    LOCAL_VLM_BACKUP_PATH: str = "models/internvl2"

    # 告警推送
    DINGTALK_WEBHOOK:        str = ""
    WECOM_WEBHOOK:           str = ""
    ALERT_COOLDOWN_MINUTES:  int = 30

    # I 模块：离线 / 私有化部署
    DEPLOYMENT_MODE:          str  = "cloud"   # cloud/hybrid/intranet/airgapped
    EXTERNAL_API_ALLOWED:     bool = True
    LLM_PROVIDER_LOCAL_ONLY:  bool = False
    TELEMETRY_ENABLED:        bool = True
    AUTO_UPDATE_CHECK:        bool = True
    # 字段加密主密钥（AES-256，空则不启用字段加密）
    FIELD_ENCRYPTION_KEY:     str  = ""

    def reload(self, allowed_fields: Iterable[str] | None = None) -> dict[str, dict[str, Any]]:
        return reload_reloadable_settings(self, allowed_fields=allowed_fields)

    @field_validator("NEO4J_URI", mode="before")
    @classmethod
    def check_neo4j_uri(cls, v: str) -> str:
        if not v.startswith(("bolt://", "neo4j://")):
            raise ValueError("NEO4J_URI 必须以 bolt:// 或 neo4j:// 开头")
        return v

    @field_validator("JWT_SECRET", mode="before")
    @classmethod
    def check_jwt_secret(cls, v: str, info: ValidationInfo) -> str:
        import os
        _DEFAULT = "aviation-jwt-secret-change-in-production"
        debug_value = info.data.get("DEBUG")
        app_env = str(info.data.get("APP_ENV") or "").lower()
        env_debug = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")
        is_dev_mode = bool(debug_value) or app_env in ("development", "dev", "local") or env_debug
        if v == _DEFAULT:
            if is_dev_mode:
                import logging
                logging.getLogger(__name__).warning("⚠️  JWT_SECRET 使用默认值，仅限开发环境！")
            else:
                raise ValueError(
                    "生产环境必须设置 JWT_SECRET 环境变量（当前为默认值）。"
                    "如在开发环境请设置 DEBUG=true。"
                )
        if len(v) < 32:
            raise ValueError("JWT_SECRET 长度至少需要 32 个字符")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def _load_reloadable_env_values(fields: Iterable[str]) -> dict[str, Any]:
    file_values = dotenv_values(ENV_FILE_PATH)
    env_values: dict[str, Any] = {}
    for field in fields:
        value = file_values.get(field)
        if value is not None:
            env_values[field] = value
            continue
        if field in os.environ:
            env_values[field] = os.environ[field]
    return env_values


def get_reloadable_settings_snapshot() -> dict[str, Any]:
    return {field: getattr(settings, field) for field in sorted(RELOADABLE_FIELDS)}


def reload_reloadable_settings(
    current: Settings | None = None,
    allowed_fields: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    target = current or settings
    fields = tuple(sorted(set(allowed_fields or RELOADABLE_FIELDS)))
    if not fields:
        return {}

    overrides = _load_reloadable_env_values(fields)
    if not overrides:
        return {}

    with _SETTINGS_LOCK:
        merged = target.model_dump()
        merged.update(overrides)
        fresh = type(target).model_validate(merged)

        changed: dict[str, dict[str, Any]] = {}
        model_fields = type(fresh).model_fields
        for field in fields:
            if field not in model_fields:
                continue
            old_value = getattr(target, field)
            new_value = getattr(fresh, field)
            if old_value != new_value:
                object.__setattr__(target, field, new_value)
                changed[field] = {"old": old_value, "new": new_value}
        return changed
