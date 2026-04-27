import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .startup import lifespan
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
from .routers.graph_api.tour     import router as graph_tour_router
from .routers.query              import router as query_router
from .routers.sessions           import router as sessions_router
from .routers.auth               import router as auth_router
from .routers.settings           import router as settings_router
from .routers.users              import router as users_router
from .routers.feedback           import router as feedback_router
from .routers.conversations      import router as conversations_router
from .routers.admin_api.entities import router as admin_entities_router
from .routers.admin_api.activity import router as admin_activity_router
from .routers.admin_api.analytics import router as admin_analytics_router
from .routers.admin_api.dashboard import router as admin_dashboard_router
from .routers.admin_api.batch_ingest import router as admin_batch_ingest_router
from .routers.admin_api.eval     import router as admin_eval_router
from .routers.admin_api.conflicts import router as admin_conflicts_router
from .routers.admin_api.usage    import router as admin_usage_router
from .routers.admin_api.ops      import router as admin_ops_router
from .routers.mobile             import router as mobile_router
from .routers.graph_api.gnn      import router as gnn_router
from .routers.graph_api.visual_qc import router as visual_qc_router
from .routers.docs.reprocess     import router as reprocess_router
from .routers.admin_api.cache    import router as admin_cache_router
from .routers.annotations        import router as annotations_router
from .routers.ai_status          import router as ai_status_router
from .routers.graph_api.references import router as graph_references_router
from .routers.favorites          import router as favorites_router
from .routers.search_api.autocomplete import router as search_autocomplete_router
from .routers.docs.ingest        import router as ingest_router, UPLOAD_DIR
from .routers.pipeline           import router as pipeline_router

from .services.infra.health import health_monitor
from .services.ops.presence_service import track_request_activity

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)

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
        "http://127.0.0.1:3000",
        settings.FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def activity_presence_middleware(request: Request, call_next):
    track_request_activity(
        request.headers.get("authorization", ""),
        request.url.path,
    )
    return await call_next(request)


@app.get("/api/health")
async def health():
    import time
    services = health_monitor.to_dict()
    overall  = "OK" if all(v["state"] == "ok" for v in services.values()) else "DEGRADED"
    return {
        "status":   overall,
        "version":  settings.APP_VERSION,
        "services": services,
        "time":     int(time.time()),
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
app.include_router(graph_tour_router)
app.include_router(query_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(users_router)
app.include_router(feedback_router)
app.include_router(conversations_router)
app.include_router(admin_entities_router)
app.include_router(admin_activity_router)
app.include_router(admin_analytics_router)
app.include_router(admin_dashboard_router)
app.include_router(admin_batch_ingest_router)
app.include_router(admin_eval_router)
app.include_router(admin_conflicts_router)
app.include_router(admin_usage_router)
app.include_router(admin_ops_router)
app.include_router(gnn_router)
app.include_router(visual_qc_router)
app.include_router(reprocess_router)
app.include_router(admin_cache_router)
app.include_router(annotations_router)
app.include_router(ai_status_router)
app.include_router(graph_references_router)
app.include_router(favorites_router)
app.include_router(search_autocomplete_router)
app.include_router(pipeline_router)

app.mount("/uploads/images", StaticFiles(directory=str(UPLOAD_DIR / "images")), name="uploads_images")
