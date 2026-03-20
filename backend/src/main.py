from fastapi import FastAPI, Depends, UploadFile, File
import shutil
from pathlib import Path
from pydantic import BaseModel
from .core.config import settings
from .core.database import init_db, get_driver
from .services.parser import parse
from .models.schemas import DocumentSchema
from contextlib import asynccontextmanager
from .services.neo4j_writer import write_document
from .routers.query import router as query_router

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        yield
    finally:
        get_driver().close()

class HealthResponse(BaseModel):
    status: str
    version: str

class StatsResponse(BaseModel):
    node_count: int

app = FastAPI(
    title="航空工艺规范 GraphRAG 知识库",
    lifespan=lifespan
    )

app.include_router(query_router)

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return { "status": "OK", "version": settings.APP_VERSION }

@app.get("/api/stats", response_model=StatsResponse)
async def stats(driver=Depends(get_driver)):
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS total")
        record = result.single()
        return {"node_count": record["total"]}

@app.post("/api/preview", response_model=DocumentSchema)
async def preview(file: UploadFile = File(...)):
    # 第一步：把上传的文件保存到 uploads/ 目录
    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # 第二步：解析 PDF
    result = parse(tmp_path)

    return result

@app.post("/api/ingest")
async def ingest(file: UploadFile = File(...), driver = Depends(get_driver)):
    # 保存文件
    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    # 解析
    doc = parse(tmp_path)

    # 写入图谱
    write_document(doc)

    return {
        "status": "OK",
        "doc_id": doc.doc_id,
        "sections": doc.total_sections,
    }