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
from .db.session import init_tables
from .services.milvus_store import connect_milvus, get_or_create_collection
from .core.config import settings

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_tables()
    # 初始化 Neo4j
    init_db()
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
    title="航空工艺规范 GraphRAG 知识库",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(sessions_router)
app.include_router(documents_router)
app.include_router(graph_router)
app.include_router(query_router)
app.include_router(auth_router)

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