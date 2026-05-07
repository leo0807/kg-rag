from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
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
    APP_VERSION:  str = "1.0.0"

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
