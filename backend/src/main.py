from fastapi import FastAPI, Depends
from pydantic import BaseModel
from .core.config import settings
from .core.database import init_db, get_driver
from contextlib import asynccontextmanager

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

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return { "status": "OK", "version": settings.APP_VERSION }

@app.get("/api/stats", response_model=StatsResponse)
async def stats(driver=Depends(get_driver)):
    with driver.session() as session:
        result = session.run("MATCH (n) RETURN count(n) AS total")
        record = result.single()
        return {"node_count": record["total"]}