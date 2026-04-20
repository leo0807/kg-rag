import logging
import uuid
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from neo4j import Driver
from pydantic import BaseModel
import shutil
from pathlib import Path
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
from .routers.admin_dashboard    import router as admin_dashboard_router
from .routers.admin_batch_ingest import router as admin_batch_ingest_router
from .routers.mobile             import router as mobile_router
from .routers.gnn                import router as gnn_router
from .routers.visual_qc          import router as visual_qc_router
from .routers.reprocess          import router as reprocess_router
from .routers.admin_cache        import router as admin_cache_router
from .routers.annotations        import router as annotations_router
from .routers.ai_status          import router as ai_status_router
from .routers.graph_references   import router as graph_references_router
from .routers.favorites          import router as favorites_router
from .routers.search_autocomplete import router as search_autocomplete_router
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
app.include_router(admin_batch_ingest_router)
app.include_router(gnn_router)
app.include_router(visual_qc_router)
app.include_router(reprocess_router)
app.include_router(admin_cache_router)
app.include_router(annotations_router)
app.include_router(ai_status_router)
app.include_router(graph_references_router)
app.include_router(favorites_router)
app.include_router(search_autocomplete_router)

# 仅挂载图片目录，文档原文通过受控接口访问
app.mount("/uploads/images", StaticFiles(directory=str(UPLOAD_DIR / "images")), name="uploads_images")

# ── 后台入库任务状态存储 ───────────────────────────────────────────────────
# key: task_id  value: {status, step, doc_id, sections, error, created_at}
_ingest_tasks: dict[str, dict] = {}
INGEST_SEMAPHORE = asyncio.Semaphore(2)


def _task_update(task_id: str, **kw: object) -> None:
    if task_id in _ingest_tasks:
        _ingest_tasks[task_id].update(kw)


def _cleanup_old_tasks() -> None:
    cutoff = datetime.utcnow() - timedelta(hours=2)
    stale = [k for k, v in _ingest_tasks.items()
             if v.get("created_at", datetime.utcnow()) < cutoff]
    for k in stale:
        _ingest_tasks.pop(k, None)

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
    w, h = img.width, max(img.height, 1)
    aspect = w / h
    area = w * h
    caption = (getattr(img, "caption", "") or "").lower()
    logo_terms = ["logo", "标志", "徽标", "商标", "公司标识", "公司logo"]
    if any(t in caption for t in logo_terms):
        return True
    # 极端长条/细条图
    if aspect > 4.0 or aspect < 0.25:
        return True
    # 面积很小（多为装饰/Logo）
    if area < 200 * 200:
        return True
    # 封面/前两页的小图
    if img.page <= 2 and (w < 320 and h < 320):
        return True
    return False


def _save_upload_file(file: UploadFile, path: Path) -> None:
    """同步文件写入，放到线程中执行，避免阻塞事件循环"""
    with path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

@app.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return parse(tmp_path)

async def _run_ingest_bg(task_id: str, tmp_path: Path, driver: Driver) -> None:
    """后台执行文档入库全流程，结果写入 _ingest_tasks[task_id]。"""
    doc = None
    section_dicts: list[dict] = []
    try:
        async with INGEST_SEMAPHORE:
            _task_update(task_id, step="parsing")
            doc = await asyncio.to_thread(parse, tmp_path)

            # 解析完成后立即将文件重命名为 {doc_id}.{ext}，
            # 使 _find_doc_file 能够通过 doc_id glob 定位原文件。
            stable_path = UPLOAD_DIR / f"{doc.doc_id}{tmp_path.suffix.lower()}"
            if tmp_path != stable_path:
                tmp_path.replace(stable_path)
                tmp_path = stable_path

            _task_update(task_id, step="checking")
            with driver.session() as session:
                rec = session.run(
                    "MATCH (d:Document {name: $doc_id}) WHERE d.title IS NOT NULL RETURN count(d) AS cnt",
                    doc_id=doc.doc_id,
                ).single()
            if rec and rec["cnt"] > 0:
                _task_update(task_id, status="skipped", doc_id=doc.doc_id, sections=doc.total_sections)
                return

            _task_update(task_id, step="writing")
            await asyncio.to_thread(write_document, doc)

        # DOCX/DOC：在后台提前转 PDF，预览时直接命中已转换的文件，
        # 即使 LibreOffice 暂不可用也不影响主流程（静默跳过）。
        if tmp_path.suffix.lower() in (".docx", ".doc"):
            _task_update(task_id, step="converting")
            try:
                from .routers.documents import _find_soffice, PREVIEW_DIR as _PREVIEW_DIR
                _soffice = _find_soffice()
                if _soffice:
                    import subprocess as _sp
                    _pdf_out = _PREVIEW_DIR / f"{doc.doc_id}.pdf"
                    if not _pdf_out.exists():
                        await asyncio.to_thread(
                            lambda: _sp.run(
                                [_soffice, "--headless", "--convert-to", "pdf",
                                 "--outdir", str(_PREVIEW_DIR), str(tmp_path)],
                                check=True,
                                stdout=_sp.PIPE, stderr=_sp.PIPE,
                            )
                        )
                        logger.info("DOCX→PDF 预转换完成 doc_id=%s", doc.doc_id)
            except Exception as _ce:
                logger.warning("DOCX→PDF 预转换跳过 doc_id=%s: %s", doc.doc_id, _ce)

        section_dicts = [
            {"chunk_id": s.chunk_id, "title": s.title, "content": s.content}
            for s in doc.sections
        ]

        # ── 实体/约束提取 ──────────────────────────────────────────────────
        _task_update(task_id, step="entities")
        try:
            from .services.entity_extractor import (
                extract_entities_from_sections,
                extract_constraints_from_sections,
            )
            from .services.entity_writer import write_entities, write_constraints

            entity_data = await asyncio.to_thread(extract_entities_from_sections, section_dicts)
            await asyncio.to_thread(write_entities, driver, doc.doc_id, entity_data)

            _task_update(task_id, step="constraints")
            constraint_data = await asyncio.to_thread(extract_constraints_from_sections, section_dicts)
            await asyncio.to_thread(write_constraints, driver, doc.doc_id, constraint_data)
        except Exception as e:
            logger.warning("实体/约束提取失败（不影响主流程）: %s", e)

        # doc.pdf_path 是解析时使用的 PDF（原生 PDF 或 .doc→PDF 临时文件）
        # 用于图片/表格提取，比原始 .doc 文件更可靠
        _pdf_for_extraction = str(doc.pdf_path) if doc.pdf_path and doc.pdf_path.exists() else str(tmp_path)

        # ── 表格约束提取 ──────────────────────────────────────────────────
        _task_update(task_id, step="tables")
        try:
            from .services.table_extractor import extract_all_tables, is_available as tables_available
            from .services.entity_writer   import write_constraints as _wc
            if tables_available():
                table_cons = await asyncio.to_thread(extract_all_tables, _pdf_for_extraction, doc.doc_id, section_dicts)
                if table_cons:
                    await asyncio.to_thread(_wc, driver, doc.doc_id, table_cons)
                    logger.info("表格约束写入 %d 条", len(table_cons))
        except Exception as e:
            logger.warning("表格提取失败（不影响主流程）: %s", e)

        # ── 多模态图片分析 ────────────────────────────────────────────────
        _task_update(task_id, step="images")
        try:
            from .services.pdf_image_extractor import extract_images_from_pdf
            from .services.image_analyzer      import analyze_image_smart
            from .services.multimodal_writer   import write_images_to_graph
            from .services.entity_writer       import link_image_tools

            images = await asyncio.to_thread(extract_images_from_pdf, _pdf_for_extraction, doc.doc_id)
            images = [img for img in images if not _is_logo(img)]

            if images:
                analyzed = []
                for img in images:
                    # 跳过已分析过的图片（重处理时去重，改用 image_id 匹配）
                    already_analyzed = False
                    try:
                        with driver.session() as _sess:
                            hit = _sess.run(
                                "MATCH (i:Image {image_id: $image_id}) "
                                "WHERE i.description IS NOT NULL AND i.description <> '' "
                                "RETURN i LIMIT 1",
                                image_id=img.image_id,
                            ).single()
                            already_analyzed = hit is not None
                    except Exception:
                        pass
                    if already_analyzed:
                        logger.info("图片已有分析记录，跳过: %s", img.image_id)
                        continue

                    # VisionService 智能路由（figure / formula 自动判断）
                    analysis = await asyncio.to_thread(
                        analyze_image_smart, img.path, img.caption, doc.doc_id
                    )

                    # 图纸深度分析（仅 figure 任务）
                    drawing: dict = {}
                    if analysis.get("task") != "formula":
                        from .services.drawing_analyzer import analyze_drawing, is_likely_drawing
                        if is_likely_drawing(analysis):
                            try:
                                drawing = await asyncio.to_thread(
                                    analyze_drawing, img.path, img.caption, doc.doc_id
                                )
                            except Exception as de:
                                logger.warning("图纸分析失败: %s", de)

                    analyzed.append({
                        "image_id":  img.image_id,
                        "page":      img.page,
                        "path":      img.path,
                        "minio_key": img.minio_key,
                        "caption":   img.caption,
                        "analysis":  analysis,
                        "drawing":   drawing,
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

        # ── MinIO 持久化 ───────────────────────────────────────────────────────
        _task_update(task_id, step="storing")
        try:
            from .core.storage import upload_file as _upload_file, BUCKET_RAW_DOCUMENTS
            minio_key = f"{doc.doc_id}{tmp_path.suffix.lower()}"
            await asyncio.to_thread(_upload_file, BUCKET_RAW_DOCUMENTS, minio_key, tmp_path)
            with driver.session() as _s:
                _s.run(
                    "MATCH (d:Document {name: $doc_id}) SET d.storage_key = $key",
                    doc_id=doc.doc_id, key=minio_key,
                )
            tmp_path.unlink(missing_ok=True)
            logger.info("文件已上传到 MinIO: %s/%s", BUCKET_RAW_DOCUMENTS, minio_key)
        except Exception as _me:
            logger.warning("MinIO 上传失败（本地文件保留作为回退）: %s", _me)
        finally:
            # 清理 .doc/.docx 转换产生的临时 PDF（图片/表格提取已完成）
            if doc and doc.pdf_path and doc.pdf_path != tmp_path:
                doc.pdf_path.unlink(missing_ok=True)

        _task_update(task_id, status="done", doc_id=doc.doc_id, sections=doc.total_sections)
        logger.info("ingest 完成 task_id=%s doc_id=%s", task_id, doc.doc_id)

    except Exception as e:
        logger.exception("ingest 后台任务失败 task_id=%s: %s", task_id, e)
        _task_update(task_id, status="error", error=str(e))


@app.post("/api/ingest")
async def ingest(
    file:   UploadFile = File(...),
    driver: Driver     = Depends(get_driver),
    _:      object     = Depends(_get_admin_user),
):
    """
    接收文件并立即返回 task_id，实际入库在后台执行。
    使用 asyncio.create_task() 而非 FastAPI BackgroundTasks，
    以确保请求依赖（含数据库连接）在响应发出后立即释放，
    避免长时间后台任务耗尽连接池。
    客户端轮询 GET /api/ingest/status/{task_id} 获取进度。
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".doc"}:
        raise HTTPException(status_code=400, detail="仅支持 PDF / DOCX / DOC 格式")

    _cleanup_old_tasks()

    task_id  = uuid.uuid4().hex[:12]
    tmp_path = UPLOAD_DIR / f"{task_id}_{file.filename or 'upload'}"

    # 文件保存在请求期间同步完成，background task 只处理已落盘的文件
    await asyncio.to_thread(_save_upload_file, file, tmp_path)

    _ingest_tasks[task_id] = {
        "status":     "running",
        "step":       "queued",
        "doc_id":     None,
        "sections":   0,
        "error":      None,
        "created_at": datetime.utcnow(),
    }
    # 用 create_task 而非 BackgroundTasks：任务与请求上下文完全解耦，
    # FastAPI 会在响应发出后立即释放所有 Depends（含 DB 连接），
    # 不会等待任务完成，从而消除连接池泄漏。
    asyncio.create_task(_run_ingest_bg(task_id, tmp_path, driver))
    return {"task_id": task_id, "status": "running"}


@app.get("/api/ingest/status/{task_id}")
async def ingest_status(task_id: str, _: object = Depends(_get_admin_user)):
    """轮询入库任务状态。status: running | done | skipped | error"""
    task = _ingest_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return {k: v for k, v in task.items() if k != "created_at"}
