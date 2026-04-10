import logging
from fastapi import FastAPI, Depends, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from neo4j import Driver
from pydantic import BaseModel
import shutil
from pathlib import Path
from fastapi import WebSocket
import asyncio

from .core.config import settings
from .core.database import get_driver
from .services.parser import parse
from .services.neo4j_writer import write_document
from .startup import lifespan
from .routers.documents          import router as documents_router
from .routers.documents_entities import router as documents_entities_router
from .routers.graph              import router as graph_router
from .routers.graph_stats        import router as graph_stats_router
from .routers.graph_tour         import router as graph_tour_router
from .routers.query              import router as query_router
from .routers.sessions           import router as sessions_router
from .routers.auth               import router as auth_router
from .routers.settings           import router as settings_router
from .routers.users              import router as users_router
from .routers.feedback           import router as feedback_router
from .routers.conversations      import router as conversations_router
from .routers.admin_entities     import router as admin_entities_router
from .routers.admin_activity     import router as admin_activity_router
from .routers.admin_analytics    import router as admin_analytics_router
from .routers.gnn                import router as gnn_router
from .routers.visual_qc          import router as visual_qc_router
from .routers.reprocess          import router as reprocess_router
from .routers.admin_cache        import router as admin_cache_router
from .auth.deps import get_admin_user as _get_admin_user

from .services.health import health_monitor

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
(UPLOAD_DIR / "images").mkdir(exist_ok=True)

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status:  str
    version: str

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    lifespan= lifespan,
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
| gnn | GraphSAGE 结构感知嵌入+全文 RRF 融合 |
| multi_hop | 多跳推理（开发中）|
    """,
    version     = "1.0.0",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # 本地开发
        "http://127.0.0.1:3000",
        settings.FRONTEND_URL,        # 生产环境
    ],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(sessions_router)
app.include_router(documents_router)
app.include_router(documents_entities_router)
app.include_router(graph_router)
app.include_router(graph_stats_router)
app.include_router(graph_tour_router)
app.include_router(query_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(users_router)
app.include_router(feedback_router)
app.include_router(conversations_router)
app.include_router(admin_entities_router)
app.include_router(admin_activity_router)
app.include_router(admin_analytics_router)
app.include_router(gnn_router)
app.include_router(visual_qc_router)
app.include_router(reprocess_router)
app.include_router(admin_cache_router)

# 挂载 uploads 目录为静态文件（图片预览）
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# 存储活跃的 WebSocket 连接
active_connections: dict[str, WebSocket] = {}

@app.websocket("/ws/ingest/{client_id}")
async def ingest_ws(websocket: WebSocket, client_id: str):
    await websocket.accept()
    active_connections[client_id] = websocket
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        active_connections.pop(client_id, None)


async def send_progress(client_id: str, message: dict):
    """向指定客户端发送进度"""
    ws = active_connections.get(client_id)
    if ws:
        try:
            await ws.send_json(message)
        except Exception:
            pass

@app.get("/api/health")
async def health():
    import time
    services = health_monitor.to_dict()
    overall  = "OK" if all(v["state"] == "ok" for v in services.values()) else "DEGRADED"
    return {
        "status":   overall,
        "version":  settings.APP_VERSION,
        "services": services,
        "time":     int(time.time()),
    }

def _is_logo(img) -> bool:
    w, h = img.width, max(img.height, 1); aspect = w / h
    return aspect > 4.0 or aspect < 0.25 or (w < 150 and h < 150) or (img.page <= 2 and aspect > 3.0)

@app.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return parse(tmp_path)

@app.post("/api/ingest")
async def ingest(
    request:   Request,
    file:      UploadFile = File(...),
    driver:    Driver     = Depends(get_driver),
    client_id: str        = "",
    _: object  = Depends(_get_admin_user),
):
    async def progress(step: str, detail: str = ""):
        if client_id:
            await send_progress(client_id, {"step": step, "detail": detail})

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail="仅支持 PDF 和 DOCX 格式")
    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    await progress("parsing", "解析文档中...")
    doc = await asyncio.to_thread(parse, tmp_path)

    await progress("checking", "检查是否已入库...")
    with driver.session() as session:
        rec = session.run(
            "MATCH (d:Document {name: $doc_id}) WHERE d.title IS NOT NULL RETURN count(d) AS cnt",
            doc_id=doc.doc_id,
        ).single()
    if rec and rec["cnt"] > 0:
        await progress("done", f"{doc.doc_id} 已入库，跳过")
        return {"status": "skipped", "doc_id": doc.doc_id, "message": f"{doc.doc_id} 已入库，跳过", "sections": doc.total_sections}

    await progress("writing", f"写入图谱，共 {doc.total_sections} 个章节...")
    await asyncio.to_thread(write_document, doc)

    # ── 实体提取：工具 / 材料 / 工序节点 + 实体间关系 ─────────────────────
    await progress("entities", "提取工具/材料/工序实体及关系...")
    try:
        from .services.entity_extractor import (
            extract_entities_from_sections,
            extract_constraints_from_sections,
        )
        from .services.entity_writer import write_entities, write_constraints

        section_dicts = [
            {"chunk_id": s.chunk_id, "title": s.title, "content": s.content}
            for s in doc.sections
        ]
        entity_data = await asyncio.to_thread(extract_entities_from_sections, section_dicts)
        await asyncio.to_thread(write_entities, driver, doc.doc_id, entity_data)

        # 工艺约束节点（力矩、公差、温度等）
        await progress("constraints", "提取工艺约束参数...")
        constraint_data = await asyncio.to_thread(extract_constraints_from_sections, section_dicts)
        await asyncio.to_thread(write_constraints, driver, doc.doc_id, constraint_data)
    except Exception as e:
        logger.warning("实体/约束提取失败（不影响主流程）: %s", e)

    # ── 表格约束提取（PP-Structure）────────────────────────
    await progress("tables", "提取技术规范表格...")
    try:
        from .services.table_extractor import extract_all_tables, is_available as tables_available
        from .services.entity_writer   import write_constraints as _wc
        if tables_available():
            table_cons = await asyncio.to_thread(extract_all_tables, str(tmp_path), doc.doc_id, section_dicts)
            if table_cons:
                await asyncio.to_thread(_wc, driver, doc.doc_id, table_cons)
                logger.info("表格约束写入 %d 条", len(table_cons))
    except Exception as e:
        logger.warning("表格提取失败（不影响主流程）: %s", e)

    # ── 多模态：提取并分析图片 ────────────────────────────
    await progress("images", "提取图片中...")
    try:
        from .services.pdf_image_extractor import extract_images_from_pdf
        from .services.image_analyzer      import analyze_image
        from .services.multimodal_writer   import write_images_to_graph
        from .services.entity_writer       import link_image_tools

        images = await asyncio.to_thread(extract_images_from_pdf, str(tmp_path), doc.doc_id)
        images = [img for img in images if not _is_logo(img)]

        if images:
            await progress("images", f"分析 {len(images)} 张图片...")
            analyzed = []
            for img in images:
                # 检查图片是否已入库并有 VLM 分析结果（缓存命中则跳过）
                already_analyzed = False
                try:
                    with driver.session() as _sess:
                        hit = _sess.run(
                            "MATCH (i:Image {path: $path}) WHERE i.description IS NOT NULL AND i.description <> '' RETURN i LIMIT 1",
                            path=img.path
                        ).single()
                        already_analyzed = hit is not None
                except Exception:
                    pass
                if already_analyzed:
                    logger.info("图片已有 VLM 分析，跳过: %s", img.path)
                    continue
                analysis = await asyncio.to_thread(analyze_image, img.path, img.caption, doc.doc_id)
                # 图纸专项分析（仅对可能是工程图纸的图片额外调用）
                drawing = {}
                from .services.drawing_analyzer import analyze_drawing, is_likely_drawing
                if is_likely_drawing(analysis):
                    try:
                        drawing = await asyncio.to_thread(analyze_drawing, img.path, img.caption, doc.doc_id)
                    except Exception as de:
                        logger.warning("图纸分析失败: %s", de)
                analyzed.append({
                    "image_id": img.image_id,
                    "page":     img.page,
                    "path":     img.path,
                    "caption":  img.caption,
                    "analysis": analysis,
                    "drawing":  drawing,
                })
            await asyncio.to_thread(write_images_to_graph, driver, doc.doc_id, analyzed)
            from .services.entity_writer import write_drawing_constraints
            for item in analyzed:
                link_image_tools(driver, item["image_id"], item.get("analysis", {}).get("tools", []))
                if anns := item.get("drawing", {}).get("annotations", []):
                    write_drawing_constraints(driver, item["image_id"], doc.doc_id, anns)
            logger.info("多模态写入完成 doc_id=%s images=%d", doc.doc_id, len(analyzed))
    except Exception as e:
        logger.warning("多模态处理失败（不影响主流程）: %s", e)

    await progress("done", f"{doc.doc_id} 写入完成")
    return {"status": "OK", "doc_id": doc.doc_id, "sections": doc.total_sections}