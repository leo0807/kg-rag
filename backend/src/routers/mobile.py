"""
src/routers/mobile.py
移动端/现场辅助专用 API：离线包下载、拍照搜索
"""
import logging
import uuid
import time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from neo4j import Driver
from pathlib import Path
import shutil

from ..core.database import get_driver
from ..services.images.image_analyzer import analyze_image
from .query.sync import query_sync
from .query.models import QueryRequest
from ..auth.deps import get_current_user
from ..db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/mobile", tags=["mobile"])

UPLOAD_DIR = Path("uploads") / "mobile_search"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/documents/{doc_id}/bundle")
async def get_offline_bundle(
    doc_id: str,
    driver: Driver = Depends(get_driver),
    _: User = Depends(get_current_user),
):
    """
    获取离线数据包：文档元数据 + 全文章节 + 关联图谱子集。
    供移动端在弱网环境下离线展示。
    """
    with driver.session() as session:
        # 1. 文档元数据
        doc_res = session.run("""
            MATCH (d:Document {name: $doc_id})
            RETURN d.name AS doc_id, d.title AS title, d.version AS version, d.issue_date AS issue_date
        """, doc_id=doc_id).single()
        if not doc_res:
            raise HTTPException(404, f"文档不存在: {doc_id}")
        
        # 2. 所有章节内容
        sec_res = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            RETURN s.chunk_id AS chunk_id, s.number AS number, s.title AS title, s.content AS content
            ORDER BY s.number
        """, doc_id=doc_id)
        sections = [dict(r) for r in sec_res]
        
        # 3. 关联实体与关系（图谱投影）
        # 提取与该文档章节直接关联的所有实体
        graph_res = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            OPTIONAL MATCH (s)-[r]->(e)
            WHERE e:Tool OR e:Material OR e:Process OR e:Constraint OR e:Table
            RETURN s.chunk_id AS source, e.name AS target_name, 
                   elementId(e) AS target_id, labels(e)[0] AS target_type, 
                   type(r) AS rel_type, properties(e) AS properties
        """, doc_id=doc_id)
        
        nodes_map = {}
        edges = []
        for r in graph_res:
            if not r["target_id"]: continue
            
            # 添加目标节点
            t_id = r["target_id"]
            if t_id not in nodes_map:
                nodes_map[t_id] = {
                    "id": t_id,
                    "name": r["target_name"] or t_id,
                    "type": r["target_type"],
                    "properties": r["properties"]
                }
            
            # 添加关系
            edges.append({
                "source": r["source"],
                "target": t_id,
                "type": r["rel_type"]
            })

    return {
        "document": dict(doc_res),
        "sections": sections,
        "graph": {
            "nodes": list(nodes_map.values()),
            "edges": edges
        },
        "generated_at": int(time.time())
    }

@router.post("/photo-search")
async def photo_search(
    request: Request,
    file: UploadFile = File(...),
    strategy: str = "parallel",
    driver: Driver = Depends(get_driver),
    user: User = Depends(get_current_user),
):
    """
    现场拍照搜索：分析图片内容并执行 RAG 检索。
    1. 上传图片并保存
    2. VLM 提取关键词与描述
    3. 执行 GraphRAG 搜索
    """
    # 1. 保存临时图片
    ext = Path(file.filename or "image.jpg").suffix
    tmp_name = f"{uuid.uuid4().hex}{ext}"
    tmp_path = UPLOAD_DIR / tmp_name
    
    with tmp_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
        
    try:
        # 2. VLM 分析
        analysis = analyze_image(str(tmp_path), caption="现场拍照上传")
        
        # 构造查询词：优先使用提取的关键词，如果没有则使用描述
        query_text = " ".join(analysis.get("keywords", []))
        if not query_text:
            query_text = analysis.get("description", "现场工艺咨询")
            
        logger.info("移动端拍照搜索: user=%s query='%s'", user.username, query_text)
        
        # 3. 执行 RAG 检索（调用同步查询核心）
        req = QueryRequest(
            question=query_text,
            strategy=strategy,
            top_k=5
        )
        
        rag_res = await query_sync(
            request=request,
            req=req,
            driver=driver,
            current_user=user
        )
        
        return {
            "analysis": analysis,
            "query_text": query_text,
            "results": rag_res
        }
    finally:
        # 搜索完成后清理图片（或者保留作为审计，这里先清理）
        if tmp_path.exists():
            tmp_path.unlink()
