from fastapi import FastAPI, Depends, UploadFile, File
import shutil
from pathlib import Path
from pydantic import BaseModel
from contextlib import asynccontextmanager
from .core.config import settings
from .core.database import init_db, get_driver
from .services.parser import parse
from .models.schemas import DocumentSchema
from .services.neo4j_writer import write_document

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
    lifespan=lifespan,
)

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return {"status": "OK", "version": settings.APP_VERSION}

@app.get("/api/stats", response_model=StatsResponse)
async def stats(driver=Depends(get_driver)):
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS total")
        record = result.single()
        return {"node_count": record["total"]}

@app.post("/api/preview", response_model=DocumentSchema)
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

@app.get("/api/documents")
async def list_documents(driver=Depends(get_driver)):
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document)
            OPTIONAL MATCH (d)-[:HAS_SECTION]->(s)
            RETURN d.name        AS doc_id,
                   d.title       AS title,
                   d.version     AS version,
                   d.issue_date  AS issue_date,
                   count(s)      AS section_count
            ORDER BY d.name
        """)
        return [dict(r) for r in result]