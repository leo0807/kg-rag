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
    from sqlalchemy import text
    from .schema_sync import sync_schema, ensure_default_tenant
    async with engine.begin() as conn:
        changes = await sync_schema(conn)
        if changes:
            logger.info("init_tables: added %d column(s): %s", len(changes), changes)

        # conversations branch FK (idempotent)
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

        await ensure_default_tenant(conn)
