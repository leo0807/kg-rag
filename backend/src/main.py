import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, UploadFile, File, Request
from neo4j import Driver
from pydantic import BaseModel
import shutil
from pathlib import Path

from .core.config import settings
from .core.database import init_db, get_driver
from .services.parser import parse
from .services.neo4j_writer import write_document
from .routers.documents import router as documents_router
from .routers.graph import router as graph_router
from .routers.query import router as query_router
from .routers.sessions import router as sessions_router
from .routers.auth import router as auth_router
from .routers.settings import router as settings_router
from .routers.users import router as users_router

from .db.session import init_tables
from .services.milvus_store import connect_milvus, get_or_create_collection
from .core.config import settings
from .core.logging import setup_logging


from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("CPS 知识库 v%s 启动中...", settings.APP_VERSION)
    # 启动检查
    logger.info("=" * 50)
    logger.info("CPS 知识库 v%s 启动中...", settings.APP_VERSION)
    logger.info("NEO4J_URI:  %s", settings.NEO4J_URI)
    logger.info("MILVUS:     %s:%s", settings.MILVUS_HOST, settings.MILVUS_PORT)
    logger.info("LLM_MODE:   %s / %s", settings.LLM_MODE, settings.LLM_MODEL)
    logger.info("=" * 50)

    # 初始化 Neo4j
    init_db()

    await init_tables()

    # 初始化 Milvus
    try:
        connect_milvus(
            host=settings.MILVUS_HOST,
            port=str(settings.MILVUS_PORT),
        )
        get_or_create_collection()
        logger.info("Milvus 初始化完成")
    except Exception as e:
        logger.warning("Milvus 初始化失败: %s", e)
    print(">>> lifespan 启动：数据库连接已建立")
    yield
    get_driver().close()

class HealthResponse(BaseModel):
    status:  str
    version: str

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title       = "CPS 知识库 API",
    description = """
## 航空工艺规范 GraphRAG 智能问答系统

### 功能模块
- **认证** `/api/auth` — 用户注册、登录、密码修改
- **文档** `/api/documents` — 文档库查询、章节详情
- **查询** `/api/query` — 四策略 GraphRAG 智能问答
- **图谱** `/api/graph` — 知识图谱数据
- **会话** `/api/sessions` — 查询历史管理
- **设置** `/api/settings` — 用户模型配置
- **用户** `/api/users` — 管理员用户管理

### 检索策略
| 策略 | 说明 |
|------|------|
| parallel | 全文+向量并行，RRF融合 |
| sequential | 全文优先，不足时向量补充 |
| graph_augmented | 并行+图谱邻居扩展 |
| multi_hop | 多跳推理（开发中）|
    """,
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(sessions_router)
app.include_router(documents_router)
app.include_router(graph_router)
app.include_router(query_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(users_router)

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return {"status": "OK", "version": settings.APP_VERSION}

@app.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return parse(tmp_path)

@app.post("/api/ingest")
@limiter.limit("10/minute")
async def ingest(
    request: Request,
    file:   UploadFile = File(...),
    driver: Driver     = Depends(get_driver),
):
    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # 先解析拿到 doc_id
    doc = parse(tmp_path)

    # 检查是否已入库
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})
            WHERE d.title IS NOT NULL
            RETURN count(d) AS cnt
        """, doc_id=doc.doc_id)
        record = result.single()
        already_exists = record and record["cnt"] > 0

    if already_exists:
        return {
            "status":  "skipped",
            "doc_id":  doc.doc_id,
            "message": f"{doc.doc_id} 已入库，跳过",
            "sections": doc.total_sections,
        }

    write_document(doc)
    return {
        "status":   "OK",
        "doc_id":   doc.doc_id,
        "sections": doc.total_sections,
    }