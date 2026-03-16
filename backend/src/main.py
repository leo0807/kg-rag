from fastapi import FastAPI
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
    version: str

app = FastAPI()

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return { "status": "OK", "version": "1.0.0" }