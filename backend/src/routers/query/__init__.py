"""
src/routers/query/__init__.py
查询模块路由注册
"""
from fastapi import APIRouter, Depends, Request
from neo4j import Driver
from slowapi import Limiter
from slowapi.util import get_remote_address
from ...core.database import get_driver
from .models import QueryRequest, QueryResponse
from .sync   import query_sync
from .stream import query_stream

router  = APIRouter(prefix="/api", tags=["query"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
async def query(request: Request, req: QueryRequest, driver: Driver = Depends(get_driver)):
    return await query_sync(request, req, driver)


@router.post("/query/stream")
@limiter.limit("30/minute")
async def query_stream_route(request: Request, req: QueryRequest, driver: Driver = Depends(get_driver)):
    return await query_stream(request, req, driver)