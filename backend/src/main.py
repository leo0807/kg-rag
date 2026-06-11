import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.logging_setup import setup_logging
from .middleware.request_logging import request_logging_middleware
from .middleware.shutdown_gate import ShutdownGateMiddleware
from .middleware.body_size_limit import BodySizeLimitMiddleware
from .routers.docs.files         import router as document_files_router
from .routers.docs.analysis      import router as document_analysis_router
from .routers.docs.backfill      import router as document_backfill_router
from .routers.search_api.search  import router as search_router
from .routers.docs.documents     import router as documents_router
from .routers.docs.entities      import router as documents_entities_router
from .routers.docs.images        import router as documents_images_router
from .routers.graph_api.graph    import router as graph_router
from .routers.graph_api.graph_browse import router as graph_browse_router
from .routers.graph_api.graph_explore import router as graph_explore_router
from .routers.graph_api.stats    import router as graph_stats_router
from .routers.graph_api.schema   import router as graph_schema_router
from .routers.graph_api.tour     import router as graph_tour_router
from .routers.query              import router as query_router
from .routers.sessions           import router as sessions_router
from .routers.auth               import router as auth_router
from .routers.settings           import router as settings_router
from .routers.users              import router as users_router
from .routers.feedback           import router as feedback_router
from .routers.conversations      import router as conversations_router
from .routers.conversations_ext  import router as conversations_ext_router
from .routers.sharing            import router as sharing_router, public_router as shared_public_router
from .routers.notes              import router as notes_router
from .routers.recommend          import router as recommend_router
from .routers.wiki               import router as wiki_router
from .routers.preferences        import router as preferences_router
from .routers.admin_api.entities import router as admin_entities_router
from .routers.admin_api.activity import router as admin_activity_router
from .routers.admin_api.analytics import router as admin_analytics_router
from .routers.admin_api.dashboard import router as admin_dashboard_router
from .routers.admin_api.batch_ingest import router as admin_batch_ingest_router
from .routers.admin_api.eval     import router as admin_eval_router
from .routers.admin_api.conflicts import router as admin_conflicts_router
from .routers.admin_api.usage    import router as admin_usage_router
from .routers.admin_api.ops      import router as admin_ops_router
from .routers.admin_api.cypher   import router as admin_cypher_router
from .routers.admin_api.prompts  import router as admin_prompts_router
from .routers.mobile             import router as mobile_router
from .routers.graph_api.gnn      import router as gnn_router
from .routers.graph_api.visual_qc import router as visual_qc_router
from .routers.docs.reprocess     import router as reprocess_router
from .routers.admin_api.cache    import router as admin_cache_router
from .routers.admin_api.config_reload import router as admin_config_router
from .routers.admin_api.synonyms import router as admin_synonyms_router
from .routers.annotations        import router as annotations_router
from .routers.ai_status          import router as ai_status_router
from .routers.graph_api.references  import router as graph_references_router
from .routers.graph_api.importance   import router as graph_importance_router
from .routers.graph_api.timeline   import router as graph_timeline_router
from .routers.export               import router as export_router
from .routers.favorites          import router as favorites_router
from .routers.search_api.autocomplete import router as search_autocomplete_router
from .routers.search_api.suggest      import router as search_suggest_router
from .routers.search_api.advanced     import router as search_advanced_router
from .routers.docs.ingest        import router as ingest_router, UPLOAD_DIR
from .routers.pipeline           import router as pipeline_router
from .routers.compare            import router as compare_router
from .routers.graph_edit         import router as graph_edit_router
from .routers.knowledge_capture  import router as knowledge_capture_router
from .routers.ocr_review         import router as ocr_review_router
from .routers.entity_filter      import router as entity_filter_router
from .routers.admin_api.lab        import router as admin_lab_router
from .routers.admin_api.processing import router as admin_processing_router
from .routers.graph_api.predict    import router as graph_predict_router
from .routers.admin_api.health       import router as admin_health_router
from .routers.admin_api.associations import router as admin_associations_router
from .routers.admin_api.feedback_admin import router as admin_feedback_router
from .routers.admin_api.metrics      import router as admin_metrics_router
from .routers.admin_api.experiments  import router as admin_experiments_router
from .routers.admin_api.backup       import router as admin_backup_router
from .routers.admin_api.logs         import router as admin_logs_router
from .routers.admin_api.spec_templates import router as admin_spec_templates_router
from .routers.generation             import router as generation_router
from .routers.blueprint              import router as blueprint_router
from .routers.admin_api.eval_datasets import router as admin_eval_datasets_router
from .routers.admin_api.eval_runs     import router as admin_eval_runs_router
from .routers.admin_api.audit         import router as admin_audit_router
from .routers.admin_api.permissions   import router as admin_rbac_router
from .routers.admin_api.lifecycle     import router as admin_lifecycle_router
from .routers.admin_api.compliance    import router as compliance_router
from .routers.admin_api.data_quality  import router as admin_data_quality_router
from .routers.admin_api.doc_versions      import router as doc_versions_router
from .routers.admin_api.compliance_report import router as admin_compliance_report_router
from .middleware.audit_middleware     import AuditMiddleware
from .middleware.tenant_middleware   import TenantMiddleware
from .middleware.rate_limit          import RateLimitMiddleware
from .routers.platform.tenants       import router as platform_tenants_router
from .routers.platform.isolation     import router as platform_isolation_router
from .routers.platform.operations    import router as platform_operations_router
from .routers.admin_api.quota        import router as admin_quota_router
from .routers.admin_api.billing      import router as admin_billing_router
from .routers.admin_api.tenant_settings import router as admin_tenant_settings_router

# I 模块：离线和私有化部署
from .routers.admin_api.local_models import router as admin_local_models_router
from .routers.admin_api.security     import router as admin_security_router
from .routers.admin_api.finetune     import router as admin_finetune_router

# J 模块：数据可视化
from .routers.analytics              import router as analytics_router
from .routers.admin_api.reports      import router as admin_reports_router
from .routers.realtime               import router as realtime_router

# K 模块：工艺仿真集成
from .routers.simulation             import router as simulation_router
from .routers.simulation_ext         import router as simulation_ext_router

# H 模块：业务系统集成
from .routers.admin_api.integrations  import router as admin_integrations_router
from .routers.admin_api.webhooks      import router as admin_webhooks_router
from .routers.admin_api.api_keys      import router as admin_api_keys_router
from .routers.v1.open_api             import router as v1_open_api_router
from .routers.shopfloor               import router as shopfloor_router
from .routers.sso                     import router as sso_router
from .middleware.api_key_auth         import ApiKeyMiddleware

from .services.infra.health import health_monitor
from .services.ops.presence_service import track_request_activity

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

setup_logging(settings.LOG_LEVEL)

from .startup import lifespan

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    lifespan=lifespan,
    title="CPS 知识库 API",
    description="""
## 航空工艺规范 GraphRAG 智能问答系统

### 功能模块
- **认证** `/api/auth` — 用户注册、登录、密码修改
- **文档** `/api/documents` — 文档库查询、章节详情
- **查询** `/api/query` — 四策略 GraphRAG 智能问答
- **图谱** `/api/graph` — 知识图谱数据
- **会话** `/api/sessions` — 查询历史管理
- **设置** `/api/settings` — 用户模型配置
- **用户** `/api/users` — 管理员用户管理
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3002",
        settings.FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.MAX_REQUEST_BODY_BYTES)
app.add_middleware(AuditMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ApiKeyMiddleware)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors(include_url=False)
    safe_errors = [
        {k: (str(v) if not isinstance(v, (str, int, float, bool, list, dict, type(None))) else v)
         for k, v in e.items()} for e in errors
    ]
    logger.warning("422 validation error on %s: %s", request.url.path, safe_errors)
    return JSONResponse(status_code=422, content={"detail": safe_errors})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning("HTTP error on %s: %s %s", request.url.path, exc.status_code, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("500 unhandled on %s: %s: %s", request.url.path, type(exc).__name__, exc)
    try:
        from .db.session import AsyncSessionLocal
        from .db.models import SystemErrorEvent
        async with AsyncSessionLocal() as _db:
            _db.add(SystemErrorEvent(
                kind="server_error",
                path=str(request.url.path)[:256],
                error_type=type(exc).__name__,
                message=str(exc)[:500],
            ))
            await _db.commit()
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal error: {type(exc).__name__}"},
    )


@app.middleware("http")
async def _request_logging(request: Request, call_next):
    return await request_logging_middleware(request, call_next)


@app.middleware("http")
async def activity_presence_middleware(request: Request, call_next):
    track_request_activity(
        request.headers.get("authorization", ""),
        request.url.path,
    )
    return await call_next(request)


app.add_middleware(ShutdownGateMiddleware)


_START_TIME = __import__("time").time()

@app.get("/api/health")
async def health():
    import time
    services = health_monitor.to_dict()
    all_ok   = all(v.get("state") == "ok" for v in services.values())
    overall  = "OK" if all_ok else "DEGRADED"
    # Check postgres connectivity
    try:
        from .db.session import AsyncSessionLocal
        from sqlalchemy import text as _text
        async with AsyncSessionLocal() as _db:
            await _db.execute(_text("SELECT 1"))
        services["postgres"] = {"state": "ok", "latency_ms": 0}
    except Exception as _e:
        services["postgres"] = {"state": "down", "error": str(_e)[:100]}
        overall = "DEGRADED"
    return {
        "status":         overall,
        "version":        settings.APP_VERSION,
        "services":       services,
        "uptime_seconds": int(time.time() - _START_TIME),
        "time":           int(time.time()),
    }


app.include_router(ingest_router)
app.include_router(sessions_router)
app.include_router(document_files_router)
app.include_router(document_analysis_router)
app.include_router(document_backfill_router)
app.include_router(search_router)
app.include_router(documents_router)
app.include_router(documents_entities_router)
app.include_router(documents_images_router)
app.include_router(graph_router)
app.include_router(graph_browse_router)
app.include_router(graph_explore_router)
app.include_router(graph_stats_router)
app.include_router(graph_schema_router)
app.include_router(graph_tour_router)
app.include_router(query_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(users_router)
app.include_router(feedback_router)
app.include_router(conversations_ext_router)  # must be before conversations_router: /categories before /{conv_id}
app.include_router(conversations_router)
app.include_router(sharing_router)
app.include_router(shared_public_router)
app.include_router(notes_router)
app.include_router(recommend_router)
app.include_router(wiki_router)
app.include_router(preferences_router)
app.include_router(admin_entities_router)
app.include_router(admin_activity_router)
app.include_router(admin_analytics_router)
app.include_router(admin_dashboard_router)
app.include_router(admin_batch_ingest_router)
app.include_router(admin_eval_router)
app.include_router(admin_conflicts_router)
app.include_router(admin_usage_router)
app.include_router(admin_ops_router)
app.include_router(admin_cypher_router)
app.include_router(admin_prompts_router)
app.include_router(gnn_router)
app.include_router(visual_qc_router)
app.include_router(reprocess_router)
app.include_router(admin_cache_router)
app.include_router(admin_config_router)
app.include_router(admin_synonyms_router)
app.include_router(annotations_router)
app.include_router(ai_status_router)
app.include_router(graph_references_router)
app.include_router(graph_importance_router)
app.include_router(graph_timeline_router)
app.include_router(export_router)
app.include_router(favorites_router)
app.include_router(search_autocomplete_router)
app.include_router(search_suggest_router)
app.include_router(search_advanced_router)
app.include_router(pipeline_router)
app.include_router(compare_router)
app.include_router(graph_edit_router)
app.include_router(knowledge_capture_router)
app.include_router(ocr_review_router)
app.include_router(entity_filter_router)
app.include_router(admin_lab_router)
app.include_router(admin_processing_router)
app.include_router(graph_predict_router)
app.include_router(admin_health_router)
app.include_router(admin_associations_router)
app.include_router(admin_feedback_router)
app.include_router(admin_metrics_router)
app.include_router(admin_experiments_router)
app.include_router(admin_backup_router)
app.include_router(admin_logs_router)
app.include_router(admin_spec_templates_router)
app.include_router(generation_router)
app.include_router(blueprint_router)
app.include_router(admin_eval_datasets_router)
app.include_router(admin_eval_runs_router)
app.include_router(admin_audit_router)
app.include_router(admin_rbac_router)
app.include_router(admin_lifecycle_router)
app.include_router(compliance_router)
app.include_router(admin_data_quality_router)
app.include_router(doc_versions_router)
app.include_router(admin_compliance_report_router)

# I 模块：离线和私有化部署
app.include_router(admin_local_models_router)
app.include_router(admin_security_router)
app.include_router(admin_finetune_router)

# J 模块：数据可视化
app.include_router(analytics_router)
app.include_router(admin_reports_router)
app.include_router(realtime_router)

# K 模块：工艺仿真集成
app.include_router(simulation_router)
app.include_router(simulation_ext_router)

# H 模块：业务系统集成
app.include_router(admin_integrations_router)
app.include_router(admin_webhooks_router)
app.include_router(admin_api_keys_router)
app.include_router(v1_open_api_router)
app.include_router(shopfloor_router)
app.include_router(sso_router)

# G 模块：多租户支持
app.include_router(platform_tenants_router)
app.include_router(platform_isolation_router)
app.include_router(platform_operations_router)
app.include_router(admin_quota_router)
app.include_router(admin_billing_router)
app.include_router(admin_tenant_settings_router)

app.mount("/uploads/images", StaticFiles(directory=str(UPLOAD_DIR / "images")), name="uploads_images")
