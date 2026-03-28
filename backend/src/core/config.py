from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ROOT / ".env"),
        extra="ignore",
    )

    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    # 数据库
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "aviation123"
    
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530  

    REDIS_URL: str = "redis://localhost:6379/0"

    DASHSCOPE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"   # 可换成任意本地模型
    RETRIEVER_TOP_K: int = 5           # 向量召回数量

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST:       str = "http://localhost:3001"

    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530

    # Embedding 配置
    EMBEDDING_MODE:     str = "local"          # local | api
    EMBEDDING_MODEL:    str = "models/bge-m3"  # 本地路径或模型名
    EMBEDDING_API_URL:  str = ""               # API 模式时的端点
    EMBEDDING_API_KEY:  str = ""               # API 模式时的密钥

    # Reranker 配置
    RERANKER_MODE:      str = "local"
    RERANKER_MODEL:     str = "models/bge-reranker-v2-m3"
    RERANKER_API_URL:   str = ""
    RERANKER_API_KEY:   str = ""

    # LLM 配置（用于答案生成，待接入）
    LLM_MODE:           str = "api"            # local | api
    LLM_API_URL:        str = "http://localhost:11434/v1"  # Ollama
    LLM_API_KEY:        str = "ollama"
    LLM_MODEL:          str = "qwen2.5:7b"

    DATABASE_URL: str = "postgresql+asyncpg://aviation:aviation123@localhost:5432/aviation"

    JWT_SECRET:       str = "aviation-jwt-secret-change-in-production"
    JWT_EXPIRE_HOURS: int = 24

    # LLM 配置
    LLM_MODE:    str = "openai"                        # openai | anthropic
    LLM_API_URL: str = "http://localhost:11434/v1"     # Ollama 默认地址
    LLM_API_KEY: str = "ollama"                        # Ollama 不需要真实 key
    LLM_MODEL:   str = "qwen2.5:7b"                   # 默认模型

    REDIS_URL:         str = "redis://localhost:6379/0"
    QUERY_CACHE_TTL:   int = 3600  # 缓存1小时

    LOG_LEVEL: str = "INFO"
    DEBUG:     bool = True   # 开发时 True，生产时 False

    APP_VERSION: str = "1.0.0"

    @field_validator("NEO4J_URI", mode="before")
    @classmethod
    def check_neo4j_uri(cls, v: str) -> str:
        if not v.startswith(("bolt://", "neo4j://")):
            raise ValueError("NEO4J_URI 必须以 bolt:// 或 neo4j:// 开头")
        return v

    @field_validator("JWT_SECRET", mode="before")
    @classmethod
    def check_jwt_secret(cls, v: str) -> str:
        if v == "aviation-jwt-secret-change-in-production":
            import logging
            logging.getLogger(__name__).warning(
                "⚠️  JWT_SECRET 使用默认值，生产环境请修改！"
            )
        if len(v) < 16:
            raise ValueError("JWT_SECRET 至少需要16个字符")
        return v
@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()