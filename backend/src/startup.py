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
from .core.config_watcher import config_watcher
from .core.logging_setup import setup_logging
from .core.shutdown import shutdown_tracker
from .db.session import AsyncSessionLocal, init_tables
from .services.infra.health import health_monitor
from .services.retrieval.embedder import get_cached_embedding
from .services.storage.milvus_store import connect_milvus, get_or_create_collection
from .services.storage.es_store import init_es_index
from .core.storage import ensure_buckets

logger = logging.getLogger(__name__)


def _setup_otel() -> None:
    """初始化 OpenTelemetry TracerProvider。

    通过 OTEL_EXPORTER_OTLP_ENDPOINT 环境变量启用，未设置则 no-op（零开销）。
    示例（Jaeger / Grafana Tempo）：
      OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318
    """
    import os as _os
    endpoint = _os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").rstrip("/")
    if not endpoint:
        return
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    resource = Resource.create({
        SERVICE_NAME: "kg-rag-backend",
        SERVICE_VERSION: settings.APP_VERSION,
    })
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
    )
    trace.set_tracer_provider(provider)
    logger.info("OpenTelemetry TracerProvider 已初始化，导出至 %s", endpoint)


_setup_otel()

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

    # F2.2: seed built-in RBAC roles/permissions
    try:
        from .services.auth.rbac_seed import seed_rbac
        async with AsyncSessionLocal() as _db:
            await seed_rbac(_db)
    except Exception as _e:
        logger.warning("RBAC seed failed (non-fatal): %s", _e)

    # F3.1: seed default retention policies
    try:
        from .services.governance.lifecycle_runner import seed_default_policies
        async with AsyncSessionLocal() as _db:
            await seed_default_policies(_db)
    except Exception as _e:
        logger.warning("Lifecycle policy seed failed (non-fatal): %s", _e)

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
        try:
            from .services.governance.lifecycle_runner import run_lifecycle
            scheduler.add_job(run_lifecycle, "cron", hour=2, minute=0,
                              id="lifecycle_runner", replace_existing=True)
        except Exception as _e:
            logger.warning("Failed to schedule lifecycle runner: %s", _e)
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

    # 启动告警规则定期评估（每5分钟）
    async def _alert_loop() -> None:
        import asyncio as _asyncio
        from .services.monitoring.alert_rules import evaluate_rules
        while True:
            await _asyncio.sleep(300)
            try:
                await evaluate_rules()
            except Exception as _e:
                logger.debug("告警规则评估异常: %s", _e)

    asyncio.create_task(_alert_loop())

    try:
        await asyncio.to_thread(get_cached_embedding, "启动预热")
        logger.info("Embedding 预热完成")
    except Exception as e:
        logger.warning("Embedding 预热失败: %s", e)

    await config_watcher.start()

    # ... (existing GNN service logic)

    # 服务重启后图片补全任务不自动续跑，由用户在管理页面手动控制
    # Redis 中的进度数据保留，用户点击"启动任务"时从断点继续

    # H6 Webhook dispatcher 初始化
    try:
        from .services.integration.webhook_dispatcher import init_dispatcher
        from .db.session import AsyncSessionLocal
        init_dispatcher(AsyncSessionLocal)
        logger.info("WebhookDispatcher 已初始化")
    except Exception as e:
        logger.warning("WebhookDispatcher 初始化失败: %s", e)

    # I1 离线 / 私有化部署模式检测
    try:
        from .core.deployment_mode import deployment_checker
        mode = await deployment_checker.detect_mode()
        logger.info("部署模式: %s", mode.value)
        if mode.value == "airgapped":
            await deployment_checker.enforce_airgap()
        elif mode.value == "intranet":
            results = await deployment_checker.validate_offline_ready()
            if not results.get("local_llm_available"):
                logger.warning("INTRANET 模式：本地 LLM 不可用，请检查 Ollama/vLLM 是否启动")
    except RuntimeError as e:
        logger.error("部署模式检查失败: %s", e)
        raise
    except Exception as e:
        logger.warning("部署模式检测异常（非致命）: %s", e)

    print(">>> lifespan 启动：数据库连接已建立")
    yield
    logger.info("Application shutting down, draining active streams...")
    clean = await shutdown_tracker.drain(grace_period=settings.SHUTDOWN_GRACE_PERIOD_SECONDS)
    if not clean:
        logger.warning("Shutdown timed out, some streams were force-killed")
    await config_watcher.stop()
    health_monitor.stop_background_task()
    if _HAS_SCHEDULER and scheduler:
        scheduler.shutdown()
    get_driver().close()
