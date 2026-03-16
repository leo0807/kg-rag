from fastapi import FastAPI
from pydantic import BaseModel
from .core.config import settings
from .core.database import init_db, get_driver
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    # 关闭时执行
    get_driver().close()

class HealthResponse(BaseModel):
    status: str
    version: str

app = FastAPI(
    title="航空工艺规范 GraphRAG 知识库",
    lifespan=lifespan
    )

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return { "status": "OK", "version": settings.APP_VERSION }