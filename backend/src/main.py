from fastapi import FastAPI
from pydantic import BaseModel
from .core.config import settings

class HealthResponse(BaseModel):
    status: str
    version: str

app = FastAPI(title="航空工艺规范 GraphRAG 知识库")

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return { "status": "OK", "version": settings.APP_VERSION }