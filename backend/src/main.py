from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, UploadFile, File
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
    status:  str
    version: str

app = FastAPI(
    title="航空工艺规范 GraphRAG 知识库",
    lifespan=lifespan,
)

app.include_router(documents_router)
app.include_router(graph_router)
app.include_router(query_router)

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
async def ingest(file: UploadFile = File(...)):
    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    doc = parse(tmp_path)
    write_document(doc)
    return {"status": "OK", "doc_id": doc.doc_id, "sections": doc.total_sections}