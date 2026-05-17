"""
数据库会话管理
"""
import logging
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from ..core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_engine():
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=20,
        max_overflow=40,
        pool_timeout=10,       # fail fast instead of waiting 30 s
        pool_recycle=3600,     # recycle idle connections hourly
        pool_pre_ping=True,    # detect stale connections after container restarts
    )

@lru_cache(maxsize=1)
def get_sessionmaker():
    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


class _LazySessionLocal:
    def __call__(self, *args, **kwargs):
        return get_sessionmaker()(*args, **kwargs)


AsyncSessionLocal = _LazySessionLocal()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_tables():
    engine = get_engine()
    from .base import Base
    from . import models
    from ..routers import feedback  # 确保 QueryFeedback 被注册
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 增量迁移：若表已存在则补全缺失列
        for col, ctype in [
            ("detail",             "TEXT NOT NULL DEFAULT ''"),
            ("retrieval_score",    "INTEGER"),
            ("completeness_score", "INTEGER"),
            ("clarity_score",      "INTEGER"),
            ("graph_score",        "INTEGER"),
            ("comment_text",       "TEXT"),
            ("sources_count",      "INTEGER"),
        ]:
            try:
                await conn.execute(text(
                    f"ALTER TABLE query_feedback ADD COLUMN IF NOT EXISTS {col} {ctype}"
                ))
            except Exception:
                pass
