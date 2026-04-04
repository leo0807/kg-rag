import logging
from contextlib import asynccontextmanager
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
from .core.database import init_db, get_driver
from .services.parser import parse
from .services.neo4j_writer import write_document
from .routers.documents import router as documents_router
from .routers.graph import router as graph_router
from .routers.query import router as query_router
from .routers.sessions import router as sessions_router
from .routers.auth import router as auth_router
from .routers.settings import router as settings_router
from .routers.users import router as users_router
from .routers.feedback import router as feedback_router
from .routers.conversations import router as conversations_router
from .routers.admin import router as admin_router
from .routers.gnn import router as gnn_router

from .db.session import init_tables
from .services.milvus_store import connect_milvus, get_or_create_collection
from .services.health import health_monitor
from .core.config import settings
from .core.logging import setup_logging
from .services.es_store import init_es_index


from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
(UPLOAD_DIR / "images").mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("CPS 知识库 v%s 启动中...", settings.APP_VERSION)
    # 启动检查
    logger.info("=" * 50)
    logger.info("CPS 知识库 v%s 启动中...", settings.APP_VERSION)
    logger.info("NEO4J_URI:  %s", settings.NEO4J_URI)
    logger.info("MILVUS:     %s:%s", settings.MILVUS_HOST, settings.MILVUS_PORT)
    logger.info("LLM_MODE:   %s / %s", settings.LLM_MODE, settings.LLM_MODEL)
    logger.info("=" * 50)

    # 初始化 Neo4j
    init_db()

    await init_tables()

    # 首次启动：若无任何用户，自动创建默认管理员账号
    try:
        import uuid
        from sqlalchemy import select as sa_select
        from .db.session import AsyncSessionLocal
        from .db.models import User
        from .auth.password import hash_password

        async with AsyncSessionLocal() as _db:
            first_user = (await _db.execute(sa_select(User).limit(1))).scalar_one_or_none()
            if not first_user:
                _db.add(User(
                    id         = str(uuid.uuid4()),
                    username   = "000001",
                    email      = "admin@internal",
                    hashed_pw  = hash_password("admin123"),
                    full_name  = "默认管理员",
                    department = "",
                    is_admin   = True,
                    is_active  = True,
                ))
                await _db.commit()
                logger.info("已创建默认管理员账号 工号=000001 密码=admin123，请登录后及时修改密码")
    except Exception as e:
        logger.warning("默认管理员账号初始化失败（不影响主流程）: %s", e)

    # 确保 Neo4j 全文索引存在
    try:
        driver = get_driver()
        with driver.session() as session:
            result = session.run(
                "SHOW FULLTEXT INDEXES WHERE name = 'cps_fulltext_index'"
            ).single()
            if not result:
                logger.info("全文索引不存在，正在创建...")
                session.run("""
                    CREATE FULLTEXT INDEX cps_fulltext_index
                    FOR (s:Section) ON EACH [s.title, s.content, s.doc_id]
                """)
                logger.info("全文索引创建完成: cps_fulltext_index")
            else:
                logger.info("全文索引已就绪: cps_fulltext_index")
    except Exception as e:
        logger.warning("全文索引检查失败（不影响主流程）: %s", e)

    # 初始化 Milvus
    try:
        connect_milvus(
            host=settings.MILVUS_HOST,
            port=str(settings.MILVUS_PORT),
        )
        get_or_create_collection()
        logger.info("Milvus 初始化完成")
        init_es_index()
        logger.info("ES 初始化完成")
    except Exception as e:
        logger.warning("Milvus 初始化失败: %s", e)

    # 启动时全量健康检查 + 启动后台定期 ping（每 30s）
    logger.info("执行启动健康检查...")
    try:
        health_monitor.check_all()
    except Exception as e:
        logger.warning("启动健康检查异常: %s", e)
    health_monitor.start_background_task()

    # 预加载 GNN 嵌入（如已训练）
    try:
        from .services.gnn_service import get_gnn_service
        gnn_svc = get_gnn_service()
        if gnn_svc.loaded:
            logger.info("GNN 嵌入预加载完成: %d 个节点", len(gnn_svc.chunk_ids))
        else:
            logger.info("GNN 嵌入未就绪，gnn 策略将在训练后可用")
    except Exception as e:
        logger.warning("GNN 服务初始化失败（不影响其他功能）: %s", e)
    print(">>> lifespan 启动：数据库连接已建立")
    yield
    health_monitor.stop_background_task()
    get_driver().close()

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
app.include_router(graph_router)
app.include_router(query_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(users_router)
app.include_router(feedback_router)
app.include_router(conversations_router)
app.include_router(admin_router)
app.include_router(gnn_router)

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
    """
    判断提取的图片是否为 Logo/装饰图，用于排除非内容图片。
    判断依据：
    1. 宽高比极大（横幅/页眉 Logo，width/height > 4）
    2. 宽高比极小（竖版标志，height/width > 4）
    3. 尺寸偏小（100-150px 区间，装饰性图标）
    4. 出现在前两页且宽高比 > 3（封面/扉页 Logo）
    """
    w, h = img.width, max(img.height, 1)
    aspect = w / h
    if aspect > 4.0 or aspect < 0.25:
        return True
    if w < 150 and h < 150:
        return True
    if img.page <= 2 and aspect > 3.0:
        return True
    return False


@app.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return parse(tmp_path)

@app.post("/api/ingest")
@limiter.limit("10/minute")
async def ingest(
    request:   Request,
    file:      UploadFile = File(...),
    driver:    Driver     = Depends(get_driver),
    client_id: str        = "",
):
    async def progress(step: str, detail: str = ""):
        if client_id:
            await send_progress(client_id, {"step": step, "detail": detail})

    tmp_path = UPLOAD_DIR / file.filename
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    await progress("parsing", "解析 PDF 中...")
    doc = parse(tmp_path)

    await progress("checking", "检查是否已入库...")
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})
            WHERE d.title IS NOT NULL
            RETURN count(d) AS cnt
        """, doc_id=doc.doc_id)
        record = result.single()
        already_exists = record and record["cnt"] > 0

    if already_exists:
        await progress("done", f"{doc.doc_id} 已入库，跳过")
        return {
            "status":   "skipped",
            "doc_id":   doc.doc_id,
            "message":  f"{doc.doc_id} 已入库，跳过",
            "sections": doc.total_sections,
        }

    await progress("writing", f"写入图谱，共 {doc.total_sections} 个章节...")
    write_document(doc)

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
        entity_data = extract_entities_from_sections(section_dicts)
        write_entities(driver, doc.doc_id, entity_data)

        # 工艺约束节点（力矩、公差、温度等）
        await progress("constraints", "提取工艺约束参数...")
        constraint_data = extract_constraints_from_sections(section_dicts)
        write_constraints(driver, doc.doc_id, constraint_data)
    except Exception as e:
        logger.warning("实体/约束提取失败（不影响主流程）: %s", e)

    # ── 多模态：提取并分析图片 ────────────────────────────
    await progress("images", "提取图片中...")
    try:
        from .services.pdf_image_extractor import extract_images_from_pdf
        from .services.image_analyzer      import analyze_image
        from .services.multimodal_writer   import write_images_to_graph
        from .services.entity_writer       import link_image_tools

        images = extract_images_from_pdf(str(tmp_path), doc.doc_id)
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
                analysis = analyze_image(img.path, img.caption, doc.doc_id)
                analyzed.append({
                    "image_id": img.image_id,
                    "page":     img.page,
                    "path":     img.path,
                    "caption":  img.caption,
                    "analysis": analysis,
                })
            write_images_to_graph(driver, doc.doc_id, analyzed)
            # 将图片识别到的工具链接到 Tool 节点
            for item in analyzed:
                tools = item.get("analysis", {}).get("tools", [])
                link_image_tools(driver, item["image_id"], tools)
            logger.info("多模态写入完成 doc_id=%s images=%d", doc.doc_id, len(analyzed))
    except Exception as e:
        logger.warning("多模态处理失败（不影响主流程）: %s", e)

    await progress("done", f"{doc.doc_id} 写入完成")
    return {
        "status":   "OK",
        "doc_id":   doc.doc_id,
        "sections": doc.total_sections,
    }