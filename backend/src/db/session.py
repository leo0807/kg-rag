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
    from . import models, gen_models, ux_models, eval_models, rbac_models, lifecycle_models, version_models  # ensure all models registered
    from ..services.audit import audit_models as _audit_models  # noqa: F401
    from ..routers import feedback    # 确保 QueryFeedback 被注册
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
            ("accuracy",           "VARCHAR(20)"),
            ("error_types",        "TEXT"),
            ("correct_answer",     "TEXT"),
            ("chunk_ids_json",     "TEXT"),
            ("feedback_status",    "VARCHAR(20) NOT NULL DEFAULT 'pending'"),
        ]:
            try:
                await conn.execute(text(
                    f"ALTER TABLE query_feedback ADD COLUMN IF NOT EXISTS {col} {ctype}"
                ))
            except Exception:
                pass
        # F079: 对话分支
        for col, ctype in [
            ("branch_from_conversation_id", "VARCHAR(36)"),
            ("branch_from_message_index",   "INTEGER"),
        ]:
            try:
                await conn.execute(text(
                    f"ALTER TABLE conversations ADD COLUMN IF NOT EXISTS {col} {ctype}"
                ))
            except Exception:
                pass
        try:
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_branch_from_conversation_id "
                "ON conversations (branch_from_conversation_id)"
            ))
        except Exception:
            pass
        # F079: FK constraint (ON DELETE SET NULL — branch survives source deletion)
        try:
            await conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.table_constraints
                        WHERE constraint_name = 'fk_conv_branch_from'
                    ) THEN
                        ALTER TABLE conversations
                          ADD CONSTRAINT fk_conv_branch_from
                          FOREIGN KEY (branch_from_conversation_id)
                          REFERENCES conversations(id)
                          ON DELETE SET NULL;
                    END IF;
                END $$;
            """))
        except Exception:
            pass
        # B2/B3: ux_models 已通过 create_all 创建，无需手动增量迁移
        # B1: 会话管理增强列
        for col, ctype in [
            ("category_id", "VARCHAR(36)"),
            ("is_pinned",   "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("is_archived", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("tags",        "JSONB NOT NULL DEFAULT '[]'::jsonb"),
        ]:
            try:
                await conn.execute(text(
                    f"ALTER TABLE conversations ADD COLUMN IF NOT EXISTS {col} {ctype}"
                ))
            except Exception:
                pass
