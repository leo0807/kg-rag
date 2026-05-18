"""
src/startup.py
FastAPI lifespan 上下文管理器 — 应用启动/关闭钩子
"""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .core.config import settings
from .core.database import init_db, get_driver
from .core.logging_setup import setup_logging
from .core.shutdown import shutdown_tracker
from .db.session import AsyncSessionLocal, init_tables
from .services.infra.health import health_monitor
from .services.retrieval.embedder import get_cached_embedding
from .services.storage.milvus_store import connect_milvus, get_or_create_collection
from .services.storage.es_store import init_es_index
from .core.storage import ensure_buckets

logger = logging.getLogger(__name__)

# apscheduler 为可选依赖——未安装时跳过定时任务，服务仍可正常启动
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from .tasks.audit_cleanup import cleanup_audit_logs
    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    _HAS_SCHEDULER = True
except ImportError:
    scheduler = None          # type: ignore[assignment]
    _HAS_SCHEDULER = False
    logger.warning("apscheduler 未安装，定时清理任务已禁用。如需启用请运行: pip install apscheduler==3.10.4")

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

    # ... (existing user creation logic)

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
        ensure_buckets()
        logger.info("MinIO 存储桶初始化完成")
    except Exception as e:
        logger.warning("Milvus/MinIO 初始化失败: %s", e)

    # 启动定时任务（审计日志清理：每天凌晨 03:00）
    if _HAS_SCHEDULER:
        scheduler.add_job(
            cleanup_audit_logs,
            "cron",
            hour=3,
            minute=0,
            args=[365],
            id="cleanup_audit_logs",
            replace_existing=True,
        )
        scheduler.start()
        logger.info("APScheduler 已启动，审计日志清理任务 (365天保留) 已注册")

    # LibreOffice 可用性检查（仅警告，不阻断启动）
    try:
        from .services.parsing.parser import _find_soffice
        soffice = _find_soffice()
        if soffice:
            logger.info("LibreOffice 已就绪: %s", soffice)
        else:
            logger.warning(
                "LibreOffice 未找到 — 旧版 .doc 文件（二进制 OLE 格式）将无法解析。"
                "如需支持，请在 Dockerfile 中安装 libreoffice 并重新构建镜像。"
            )
    except Exception as _e:
        logger.warning("LibreOffice 检查异常: %s", _e)

    # 启动时全量健康检查 + 启动后台定期 ping（每 30s）
    logger.info("执行启动健康检查...")
    try:
        health_monitor.check_all()
    except Exception as e:
        logger.warning("启动健康检查异常: %s", e)
    health_monitor.start_background_task()

    try:
        await asyncio.to_thread(get_cached_embedding, "启动预热")
        logger.info("Embedding 预热完成")
    except Exception as e:
        logger.warning("Embedding 预热失败: %s", e)

    # ... (existing GNN service logic)

    # 服务重启后图片补全任务不自动续跑，由用户在管理页面手动控制
    # Redis 中的进度数据保留，用户点击"启动任务"时从断点继续

    print(">>> lifespan 启动：数据库连接已建立")
    yield
    logger.info("Application shutting down, draining active streams...")
    clean = await shutdown_tracker.drain(grace_period=settings.SHUTDOWN_GRACE_PERIOD_SECONDS)
    if not clean:
        logger.warning("Shutdown timed out, some streams were force-killed")
    health_monitor.stop_background_task()
    if _HAS_SCHEDULER and scheduler:
        scheduler.shutdown()
    get_driver().close()
