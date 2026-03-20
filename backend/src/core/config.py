from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../../.env",
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

    APP_VERSION: str = "1.0.0"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()