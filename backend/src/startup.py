"""
src/startup.py
FastAPI lifespan 上下文管理器 — 应用启动/关闭钩子
"""
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .core.config import settings
from .core.database import init_db, get_driver
from .core.logging import setup_logging
from .db.session import AsyncSessionLocal, init_tables
from .services.health import health_monitor
from .services.milvus_store import connect_milvus, get_or_create_collection
from .services.es_store import init_es_index

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("=" * 50)
    logger.info("CPS 知识库 v%s 启动中...", settings.APP_VERSION)
    logger.info("NEO4J_URI:  %s", settings.NEO4J_URI)
    logger.info("MILVUS:     %s:%s", settings.MILVUS_HOST, settings.MILVUS_PORT)
    logger.info("LLM_MODE:   %s / %s", settings.LLM_MODE, settings.LLM_MODEL)
    logger.info("=" * 50)

    # 初始化 Neo4j
    init_db()
    await init_tables()

    # 首次启动：若无任何用户，自动创建默认管理员账号
    try:
        from sqlalchemy import select as sa_select
        from .db.models import User
        from .auth.password import hash_password

        async with AsyncSessionLocal() as _db:
            first_user = (await _db.execute(sa_select(User).limit(1))).scalar_one_or_none()
            if not first_user:
                _db.add(User(
                    id         = str(uuid.uuid4()),
                    username   = "000001",
                    email      = "admin@internal",
                    hashed_pw  = hash_password("admin123"),
                    full_name  = "默认管理员",
                    department = "",
                    is_admin   = True,
                    is_active  = True,
                ))
                await _db.commit()
                logger.info("已创建默认管理员账号 工号=000001 密码=admin123，请登录后及时修改密码")
    except Exception as e:
        logger.warning("默认管理员账号初始化失败（不影响主流程）: %s", e)

    # 确保 Neo4j 全文索引存在
    try:
        driver = get_driver()
        with driver.session() as session:
            result = session.run(
                "SHOW FULLTEXT INDEXES WHERE name = 'cps_fulltext_index'"
            ).single()
            if not result:
                logger.info("全文索引不存在，正在创建...")
                session.run("""
                    CREATE FULLTEXT INDEX cps_fulltext_index
                    FOR (s:Section) ON EACH [s.title, s.content, s.doc_id]
                """)
                logger.info("全文索引创建完成: cps_fulltext_index")
            else:
                logger.info("全文索引已就绪: cps_fulltext_index")
    except Exception as e:
        logger.warning("全文索引检查失败（不影响主流程）: %s", e)

    # 初始化 Milvus + ES
    try:
        connect_milvus(
            host=settings.MILVUS_HOST,
            port=str(settings.MILVUS_PORT),
        )
        get_or_create_collection()
        logger.info("Milvus 初始化完成")
        init_es_index()
        logger.info("ES 初始化完成")
    except Exception as e:
        logger.warning("Milvus 初始化失败: %s", e)

    # 启动时全量健康检查 + 启动后台定期 ping（每 30s）
    logger.info("执行启动健康检查...")
    try:
        health_monitor.check_all()
    except Exception as e:
        logger.warning("启动健康检查异常: %s", e)
    health_monitor.start_background_task()

    # 预加载 GNN 嵌入（如已训练）
    try:
        from .services.gnn_service import get_gnn_service
        gnn_svc = get_gnn_service()
        if gnn_svc.loaded:
            logger.info("GNN 嵌入预加载完成: %d 个节点", len(gnn_svc.chunk_ids))
        else:
            logger.info("GNN 嵌入未就绪，gnn 策略将在训练后可用")
    except Exception as e:
        logger.warning("GNN 服务初始化失败（不影响其他功能）: %s", e)

    print(">>> lifespan 启动：数据库连接已建立")
    yield
    health_monitor.stop_background_task()
    get_driver().close()
