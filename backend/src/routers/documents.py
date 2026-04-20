import logging
import tempfile
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, Response
from neo4j import Driver
from pathlib import Path
import shutil
import subprocess
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.database import get_driver
from ..db.session import get_db
from ..db.models import AuditLog, User
from ..auth.deps import get_admin_user, get_optional_user, get_current_user
from ..auth.jwt import decode_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

DOC_UPLOAD_DIR = Path("uploads") / "docs"
DOC_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PREVIEW_DIR = Path("uploads") / "previews"
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

LEGACY_UPLOAD_DIR = Path("uploads")


def _find_doc_file(doc_id: str) -> Path | None:
    """本地文件回退查找（已迁移到 MinIO 的文档不再需要此方法）。"""
    patterns = [
        f"{doc_id}*.pdf", f"{doc_id}*.PDF",
        f"{doc_id}*.docx", f"{doc_id}*.DOCX",
        f"{doc_id}*.doc", f"{doc_id}*.DOC",
    ]
    for base in (DOC_UPLOAD_DIR, LEGACY_UPLOAD_DIR):
        for pat in patterns:
            matches = sorted(base.glob(pat))
            if matches:
                return matches[0]
    return None


def _get_storage_key(driver: Driver, doc_id: str) -> str | None:
    """从 Neo4j 读取文档的 MinIO 对象键（storage_key 属性）。"""
    with driver.session() as s:
        r = s.run(
            "MATCH (d:Document {name: $doc_id}) RETURN d.storage_key AS key",
            doc_id=doc_id,
        ).single()
        return r["key"] if r and r["key"] else None


def _convert_to_pdf(src: Path) -> Path:
    """将 .doc/.docx 转换为 PDF，使用与 parser 相同的 LibreOffice 调用方式。"""
    from ..services.parser import _find_soffice
    import os as _os

    soffice = _find_soffice()
    if not soffice:
        raise HTTPException(503, "DOC/DOCX 预览需要 LibreOffice，服务器暂未安装。")

    out = PREVIEW_DIR / f"{src.stem}.pdf"
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out

    env = _os.environ.copy()
    env["HOME"] = "/tmp"
    try:
        result = subprocess.run(
            [soffice, "--headless", "--norestore",
             "--convert-to", "pdf",
             "--outdir", str(PREVIEW_DIR), str(src)],
            capture_output=True, text=True, timeout=180, env=env,
        )
        if result.returncode != 0:
            raise HTTPException(500, f"DOC/DOCX 转换 PDF 失败: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        raise HTTPException(500, "DOC/DOCX 转换超时（>3分钟）")
    if not out.exists():
        raise HTTPException(500, "DOC/DOCX 转换 PDF 失败: 未生成预览文件")
    return out


def _cache_preview_to_minio(pdf_path: Path, preview_key: str) -> None:
    """后台任务：将转换好的 PDF 上传到 MinIO previews/ 桶作为缓存。"""
    try:
        from ..core.storage import upload_file as storage_upload, BUCKET_PREVIEWS
        storage_upload(BUCKET_PREVIEWS, preview_key, pdf_path)
        logger.info("预览缓存已上传: previews/%s", preview_key)
    except Exception as e:
        logger.warning("预览缓存上传失败（不影响本次响应）: %s", e)
    finally:
        pdf_path.unlink(missing_ok=True)


async def _get_user_from_token(token: str, db: AsyncSession) -> User:
    try:
        payload = decode_token(token)
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(401, "无效的认证凭证")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(401, "用户不存在或已禁用")
    return user

@router.get("/stats")
async def stats(driver: Driver = Depends(get_driver)):
    import json as _json
    try:
        from ..services.cache import get_redis
        r = get_redis()
        cached = r.get("neo4j:stats")
        if cached:
            return _json.loads(cached)
    except Exception:
        r = None
    with driver.session() as session:
        result = session.run("""
            MATCH (n)
            RETURN
                count(n) AS total,
                sum(CASE WHEN n:Document AND n.title IS NOT NULL THEN 1 ELSE 0 END) AS documents,
                sum(CASE WHEN n:Section THEN 1 ELSE 0 END) AS sections
        """)
        record = result.single()
        data = {"total": record["total"], "documents": record["documents"], "sections": record["sections"]}
    try:
        if r: r.setex("neo4j:stats", 60, _json.dumps(data))
    except Exception:
        pass
    return data

@router.get("/documents")
async def list_documents(
    page:     int    = 1,
    per_page: int    = 20,
    q:        str    = "",
    driver:   Driver = Depends(get_driver),
):
    import json as _json
    cache_key = f"docs:{page}:{per_page}:{q}"
    _rc = None
    try:
        from ..services.cache import get_redis
        _rc = get_redis()
        cached = _rc.get(cache_key)
        if cached:
            return _json.loads(cached)
    except Exception:
        pass
    skip = (page - 1) * per_page

    with driver.session() as session:
        # 搜索条件：匹配 doc_id 或 title
        where_clause = """
            WHERE d.title IS NOT NULL
            AND (
                $q = ''
                OR toLower(d.name)  CONTAINS toLower($q)
                OR toLower(d.title) CONTAINS toLower($q)
            )
        """

        count_result = session.run(f"""
            MATCH (d:Document)
            {where_clause}
            RETURN count(d) AS total
        """, q=q)
        total = count_result.single()["total"]

        result = session.run(f"""
            MATCH (d:Document)
            {where_clause}
            RETURN d.name        AS doc_id,
                   d.title       AS title,
                   d.version     AS version,
                   d.issue_date  AS issue_date,
                   size([(d)-[:HAS_SECTION]->(s) | s]) AS section_count,
                   size([(d)-[:HAS_IMAGE]->(i:Image) | i]) AS image_count,
                   size([(d)-[:HAS_IMAGE]->(i:Image)
                         WHERE i.analysis_level IN ['full', 'basic'] | i]) AS analyzed_image_count
            ORDER BY d.name
            SKIP $skip
            LIMIT $per_page
        """, q=q, skip=skip, per_page=per_page)

        def _analysis_status(img_count: int, analyzed: int) -> str:
            if img_count == 0:
                return "none"
            if analyzed >= img_count:
                return "analyzed"
            if analyzed > 0:
                return "partial"
            return "pending"

        documents = []
        for r in result:
            row = dict(r)
            row["analysis_status"] = _analysis_status(
                row.get("image_count", 0),
                row.get("analyzed_image_count", 0),
            )
            documents.append(row)

    out = {"data": documents, "total": total, "page": page, "per_page": per_page, "pages": (total + per_page - 1) // per_page}
    try:
        if _rc: _rc.setex(cache_key, 30, _json.dumps(out, default=str))
    except Exception:
        pass
    return out

@router.get("/documents/{doc_id}/validate")
async def validate_document(
    doc_id: str,
    driver: Driver = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    """验证单个文档的解析质量，返回结构化报告。"""
    from ..services.validator import validate_document as _validate
    result = _validate(driver, doc_id)
    return {
        "doc_id":  result.doc_id,
        "valid":   result.valid,
        "score":   result.score,
        "issues":  [{"level": i.level, "code": i.code, "detail": i.detail} for i in result.issues],
        "stats":   result.stats,
    }


@router.get("/documents/validate-all")
async def validate_all_documents(
    driver: Driver = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    """批量验证所有文档的解析质量，返回汇总报告。"""
    from ..services.validator import validate_all as _validate_all
    return _validate_all(driver)


@router.get("/documents/{doc_id}/pdf-url")
async def get_document_pdf_url(doc_id: str, driver: Driver = Depends(get_driver)):
    """返回文档预览与下载信息（兼容旧接口名）"""
    # 优先从 MinIO 获取
    storage_key = _get_storage_key(driver, doc_id)
    if storage_key:
        ext = Path(storage_key).suffix.lower().lstrip(".")
        return {
            "filename": storage_key,
            "type": ext,
            "preview_url": f"/api/documents/{doc_id}/preview",
            "download_url": f"/api/documents/{doc_id}/download",
        }
    # 回退：本地文件（迁移前上传的文档）
    src = _find_doc_file(doc_id)
    if not src:
        raise HTTPException(404, "原文文件未找到，请确认文档已上传")
    ext = src.suffix.lower().lstrip(".")
    return {
        "filename": src.name,
        "type": ext,
        "preview_url": f"/api/documents/{doc_id}/preview",
        "download_url": f"/api/documents/{doc_id}/download",
    }


def _pdf_response(data: bytes, doc_id: str) -> Response:
    """构造代理 PDF 响应，带缓存头（1 小时）。"""
    from urllib.parse import quote as _quote
    encoded = _quote(f"{doc_id}.pdf", safe="")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=\"{doc_id}.pdf\"; filename*=UTF-8''{encoded}",
            "Cache-Control": "public, max-age=3600",
            "Content-Length": str(len(data)),
        },
    )


@router.get("/documents/{doc_id}/preview")
async def preview_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    driver: Driver = Depends(get_driver),
    current_user: User | None = Depends(get_optional_user),
):
    """在线预览（PDF / DOCX / DOC），统一返回 PDF 字节流（代理模式，不依赖预签名 URL）"""
    import asyncio as _asyncio
    if token:
        await _get_user_from_token(token, db)
    elif not current_user:
        raise HTTPException(401, "缺少访问令牌")

    storage_key = _get_storage_key(driver, doc_id)
    if storage_key:
        from ..core.storage import download_bytes, object_exists, BUCKET_RAW_DOCUMENTS, BUCKET_PREVIEWS
        ext = Path(storage_key).suffix.lower()

        if ext == ".pdf":
            # PDF：直接代理字节流
            pdf_bytes = await _asyncio.to_thread(download_bytes, BUCKET_RAW_DOCUMENTS, storage_key)
            return _pdf_response(pdf_bytes, doc_id)

        # DOCX/DOC：优先从 previews/ 桶返回缓存
        preview_key = f"{doc_id}.pdf"
        if await _asyncio.to_thread(object_exists, BUCKET_PREVIEWS, preview_key):
            pdf_bytes = await _asyncio.to_thread(download_bytes, BUCKET_PREVIEWS, preview_key)
            return _pdf_response(pdf_bytes, doc_id)

        # 缓存未命中：下载原文 → LibreOffice 转 PDF → 上传缓存 → 返回
        raw_bytes = await _asyncio.to_thread(download_bytes, BUCKET_RAW_DOCUMENTS, storage_key)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(raw_bytes)
            tmp_path = Path(tmp.name)
        try:
            pdf_path = await _asyncio.to_thread(_convert_to_pdf, tmp_path)
            pdf_bytes = pdf_path.read_bytes()
            background_tasks.add_task(_cache_preview_to_minio, pdf_path, preview_key)
            return _pdf_response(pdf_bytes, doc_id)
        finally:
            tmp_path.unlink(missing_ok=True)

    # 回退：本地文件（迁移前上传的文档）
    src = _find_doc_file(doc_id)
    if not src:
        raise HTTPException(404, "原文文件未找到，请确认文档已上传")

    if src.suffix.lower() != ".pdf":
        pre_converted = PREVIEW_DIR / f"{src.stem}.pdf"
        if pre_converted.exists():
            src = pre_converted
        else:
            src = await _asyncio.to_thread(_convert_to_pdf, src)

    pdf_bytes = src.read_bytes()
    return _pdf_response(pdf_bytes, doc_id)


@router.get("/documents/{doc_id}/raw")
async def raw_document(
    doc_id: str,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    driver: Driver = Depends(get_driver),
    current_user: User | None = Depends(get_optional_user),
):
    """返回文档原始文件（需登录，不限管理员），供前端 mammoth.js 渲染 DOCX 使用。
    服务端代理：直接透传字节，不重定向到 MinIO，避免浏览器 CORS 问题。"""
    if token:
        await _get_user_from_token(token, db)
    elif not current_user:
        raise HTTPException(401, "缺少访问令牌")

    storage_key = _get_storage_key(driver, doc_id)
    if storage_key:
        from ..core.storage import download_bytes, BUCKET_RAW_DOCUMENTS
        from urllib.parse import quote as _quote
        import asyncio as _asyncio
        try:
            raw_bytes = await _asyncio.to_thread(
                download_bytes, BUCKET_RAW_DOCUMENTS, storage_key
            )
        except Exception as e:
            logger.warning("MinIO 下载失败 %s: %s", storage_key, e)
            raise HTTPException(503, "文件暂时无法访问，请稍后重试")
        ext = Path(storage_key).suffix.lower().lstrip(".")
        media_types = {
            "pdf":  "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "doc":  "application/msword",
        }
        media_type = media_types.get(ext, "application/octet-stream")
        fname = Path(storage_key).name
        encoded = _quote(fname, safe="")
        ascii_n = fname.encode("ascii", errors="replace").decode("ascii")
        return Response(
            content=raw_bytes,
            media_type=media_type,
            headers={"Content-Disposition": f"inline; filename=\"{ascii_n}\"; filename*=UTF-8''{encoded}"},
        )

    # 回退：本地文件
    src = _find_doc_file(doc_id)
    if not src:
        raise HTTPException(404, "原文文件未找到，请确认文档已上传")

    from urllib.parse import quote as _quote
    encoded = _quote(src.name, safe="")
    ascii_n  = src.name.encode("ascii", errors="replace").decode("ascii")
    ext = src.suffix.lower().lstrip(".")
    media_types = {
        "pdf":  "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc":  "application/msword",
    }
    media_type = media_types.get(ext, "application/octet-stream")
    return FileResponse(
        src,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename=\"{ascii_n}\"; filename*=UTF-8''{encoded}"},
    )


@router.get("/documents/{doc_id}/download")
async def download_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    driver: Driver = Depends(get_driver),
    admin: User = Depends(get_admin_user),
):
    """管理员下载原文文件并记录审计日志"""
    storage_key = _get_storage_key(driver, doc_id)
    if storage_key:
        db.add(AuditLog(
            user_id=admin.id,
            action="download_document",
            resource="document",
            detail=f"管理员 {admin.username} 下载了文档 {doc_id}（MinIO: {storage_key}）",
        ))
        await db.commit()
        from ..core.storage import get_url, BUCKET_RAW_DOCUMENTS
        url = get_url(BUCKET_RAW_DOCUMENTS, storage_key, expires=300)
        return RedirectResponse(url, status_code=307)

    # 回退：本地文件
    src = _find_doc_file(doc_id)
    if not src:
        raise HTTPException(404, "原文文件未找到，请确认文档已上传")

    db.add(AuditLog(
        user_id=admin.id,
        action="download_document",
        resource="document",
        detail=f"管理员 {admin.username} 下载了文档 {doc_id}（{src.name}）",
    ))
    await db.commit()

    from urllib.parse import quote as _quote
    encoded_name = _quote(src.name, safe="")
    ascii_name   = src.name.encode("ascii", errors="replace").decode("ascii")
    disposition  = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"
    return FileResponse(
        src,
        media_type="application/octet-stream",
        headers={"Content-Disposition": disposition},
    )


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, driver: Driver = Depends(get_driver)):
    with driver.session() as session:
        # 文档基本信息
        doc_result = session.run("""
            MATCH (d:Document {name: $doc_id})
            RETURN d.name AS doc_id, d.title AS title,
                   d.version AS version, d.issue_date AS issue_date
        """, doc_id=doc_id)
        doc = doc_result.single()
        if not doc:
            raise HTTPException(404, f"文档不存在: {doc_id}")

        # 章节列表（兼容新字段 number 和旧字段 section_number）
        sec_result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:HAS_SECTION]->(s:Section)
            RETURN s.chunk_id                               AS chunk_id,
                   COALESCE(s.number, s.section_number, '') AS number,
                   s.title                                  AS title,
                   s.content                                AS content
        """, doc_id=doc_id)
        # 自然排序：按 number 字段的各级数字排序（处理 "10" > "9" 和 "6.1.8" 多级）
        def _section_sort_key(row: dict):
            num = row.get("number") or ""
            try:
                return [int(p) for p in num.split(".") if p.isdigit() or (p.lstrip("-").isdigit())]
            except Exception:
                return [0]
        sections = sorted([dict(r) for r in sec_result], key=_section_sort_key)

        # 引用文件
        ref_result = session.run("""
            MATCH (d:Document {name: $doc_id})-[:REFERENCES]->(r:Document)
            RETURN r.name AS ref_id
        """, doc_id=doc_id)
        refs = [r["ref_id"] for r in ref_result]

    return {
        "doc_id":    doc["doc_id"],
        "title":     doc["title"]     or "",
        "version":   doc["version"]   or "",
        "issue_date": doc["issue_date"] or "",
        "sections":  sections,
        "refs":      refs,
    }


@router.get("/documents/{doc_id}/impact")
async def get_document_impact(
    doc_id: str,
    fresh:  bool = False,
    driver: Driver = Depends(get_driver),
):
    """
    变更影响分析：沿 REFERENCES 反向扩散，找出所有引用该文档的下游规范。
    若已有缓存属性（impact_docs），默认优先返回；fresh=true 强制实时计算。
    """
    with driver.session() as session:
        if not fresh:
            cached = session.run("""
                MATCH (d:Document {name: $doc_id})
                RETURN d.impact_docs AS impact_docs,
                       d.impact_count AS impact_count,
                       d.impact_sources AS impact_sources,
                       d.impact_generated_at AS impact_generated_at
            """, doc_id=doc_id).single()
            if cached and cached.get("impact_docs") is not None:
                return {
                    "doc_id": doc_id,
                    "impact_docs": cached.get("impact_docs") or [],
                    "impact_count": cached.get("impact_count") or 0,
                    "impact_sources": cached.get("impact_sources") or [],
                    "impact_generated_at": cached.get("impact_generated_at"),
                    "cached": True,
                }

        # 实时计算
        result = session.run("""
            MATCH (src:Document {name: $doc_id})
            OPTIONAL MATCH (src)<-[:REFERENCES*1..]-(d:Document)
            WHERE d.name IS NOT NULL AND d.name <> $doc_id
            RETURN collect(DISTINCT d.name) AS impacted
        """, doc_id=doc_id)
        impacted = result.single()["impacted"] or []
        impacted = sorted({d for d in impacted if d})
        return {
            "doc_id": doc_id,
            "impact_docs": impacted,
            "impact_count": len(impacted),
            "impact_sources": [doc_id],
            "impact_generated_at": None,
            "cached": False,
        }
@router.get("/documents/{doc_id}/versions")
async def list_document_versions(doc_id: str, driver: Driver = Depends(get_driver)):
    """获取文档的所有关联版本（向上追溯与向下覆盖）"""
    with driver.session() as session:
        result = session.run("""
            MATCH (d:Document {name: $doc_id})
            OPTIONAL MATCH (d)-[:SUPERSEDES*]-(other:Document)
            RETURN DISTINCT other.name AS doc_id, other.version AS version
            ORDER BY other.name
        """, doc_id=doc_id)
        versions = [dict(r) for r in result if r["doc_id"]]
    return {"doc_id": doc_id, "versions": versions}


@router.get("/documents/{doc_id}/compare/{other_id}")
async def compare_documents(
    doc_id:   str,
    other_id: str,
    driver:   Driver = Depends(get_driver),
):
    """
    对比两个文档的章节差异（图谱变更 + 文本 Diff）。
    doc_id: 当前版本 (New)
    other_id: 对比版本 (Old)
    """
    import difflib

    def get_text_diff(old_text: str, new_text: str) -> str:
        d = difflib.HtmlDiff()
        return d.make_file(
            (old_text or "").splitlines(),
            (new_text or "").splitlines(),
            context=True,
            numlines=3
        )

    with driver.session() as session:
        # 1. 查找图谱中的显式变更关系
        # 注意：neo4j_writer 在入库时已建立了 ADDED_SECTION / REMOVED_SECTION / CHANGED_TO
        # 这些关系是单向的 (New)-[:REL]->(Old 或 New)
        
        changes_result = session.run("""
            MATCH (new_d:Document {name: $new_id})
            MATCH (old_d:Document {name: $old_id})
            
            // 新增章节
            OPTIONAL MATCH (new_d)-[:ADDED_SECTION]->(added:Section)
            
            // 删除章节
            WITH new_d, old_d, collect(DISTINCT added.number) AS added_nums
            OPTIONAL MATCH (new_d)-[:REMOVED_SECTION]->(removed:Section)
            
            // 变更章节
            WITH new_d, old_d, added_nums, collect(DISTINCT removed.number) AS removed_nums
            OPTIONAL MATCH (old_sec:Section)<-[:CHANGED_TO]-(new_sec:Section)
            WHERE (new_d)-[:HAS_SECTION]->(new_sec) AND (old_d)-[:HAS_SECTION]->(old_sec)
            
            RETURN added_nums, removed_nums, 
                   collect(DISTINCT {new_num: new_sec.number, old_num: old_sec.number}) AS changed_pairs
        """, new_id=doc_id, old_id=other_id)
        
        changes = changes_result.single()
        added_nums   = changes["added_nums"] or []
        removed_nums = changes["removed_nums"] or []
        changed_pairs = changes["changed_pairs"] or []

        # 2. 获取两个文档的所有章节内容，用于生成详细 Diff
        def fetch_sections(d_id):
            res = session.run("""
                MATCH (d:Document {name: $id})-[:HAS_SECTION]->(s:Section)
                RETURN s.number AS number, s.title AS title, s.content AS content
                ORDER BY s.number
            """, id=d_id)
            return {r["number"]: {"title": r["title"], "content": r["content"]} for r in res}

        new_sections = fetch_sections(doc_id)
        old_sections = fetch_sections(other_id)

    # 3. 组装对比结果
    diff_report = []
    # 合并所有出现过的章节号
    all_numbers = sorted(set(new_sections.keys()) | set(old_sections.keys()))

    for num in all_numbers:
        new_s = new_sections.get(num)
        old_s = old_sections.get(num)
        
        status = "unchanged"
        if num in added_nums: status = "added"
        elif num in removed_nums: status = "removed"
        elif any(p["new_num"] == num for p in changed_pairs): status = "changed"
        elif new_s and old_s and new_s["content"] != old_s["content"]: status = "changed"

        html_diff = ""
        if status == "changed":
            # 生成简单的文本差异（为了效率，仅在有变化时生成）
            diff = difflib.ndiff(
                (old_s["content"] if old_s else "").splitlines(),
                (new_s["content"] if new_s else "").splitlines()
            )
            html_diff = "\n".join(diff)

        diff_report.append({
            "number": num,
            "title":  (new_s or old_s)["title"],
            "status": status,
            "old_content": old_s["content"] if old_s else None,
            "new_content": new_s["content"] if new_s else None,
            "diff": html_diff
        })

    return {
        "new_id": doc_id,
        "old_id": other_id,
        "changes_summary": {
            "added": len(added_nums),
            "removed": len(removed_nums),
            "changed": len([r for r in diff_report if r["status"] == "changed"])
        },
        "sections": diff_report
    }


@router.get("/sections/{chunk_id}")
async def get_section(
    chunk_id: str,
    driver:   Driver = Depends(get_driver),
):
    with driver.session() as session:
        result = session.run("""
            MATCH (s:Section {chunk_id: $chunk_id})
            RETURN COALESCE(s.number, s.section_number, '') AS number,
                   s.title                                  AS title,
                   s.content                                AS content
        """, chunk_id=chunk_id)
        record = result.single()

        if not record:
            from fastapi import HTTPException
            raise HTTPException(404, f"章节不存在: {chunk_id}")

        return dict(record)

@router.get("/search")
async def global_search(
    q:      str,
    top_k:  int    = 10,
    driver: Driver = Depends(get_driver),
):
    """全局全文搜索，跨所有文档搜索章节内容"""
    if not q.strip():
        return {"results": [], "total": 0, "query": q}

    try:
        from ..services.es_store import search_sections_es
        es_results = search_sections_es(q, top_k=top_k, highlight=True)
        results = [
            {
                "chunk_id":  r["chunk_id"],
                "doc_id":    r["doc_id"],
                "number":    r["number"],
                "title":     r["title"],
                "snippet":   "",
                "score":     r["score"],
                "highlight": r.get("highlight", {}),
            }
            for r in es_results
        ]
    except Exception as e:
        logger.warning("ES 搜索失败: %s", e)
        # 降级到 Neo4j 全文检索
        with driver.session() as session:
            result = session.run("""
                CALL db.index.fulltext.queryNodes(
                    'cps_fulltext_index', $q
                ) YIELD node, score
                RETURN node.chunk_id       AS chunk_id,
                       node.doc_id         AS doc_id,
                       node.section_number AS number,
                       node.title          AS title,
                       node.content        AS content,
                       score
                ORDER BY score DESC LIMIT $top_k
            """, q=q, top_k=top_k)
            results = [
                {
                    "chunk_id": r["chunk_id"],
                    "doc_id":   r["doc_id"],
                    "number":   r["number"] or "",
                    "title":    r["title"]  or "",
                    "snippet":  (r["content"] or "")[:200],
                    "score":    round(float(r["score"]), 4),
                    "highlight": {},
                }
                for r in result
            ]

    return {"results": results, "total": len(results), "query": q}


# ── 后台图片补全任务 ───────────────────────────────────────────────────────────

@router.post("/documents/backfill/start", summary="启动图片补全任务")
async def backfill_start(_admin=Depends(get_admin_user)):
    """
    扫描所有没有 :Image 节点的 Document，逐份从 PDF 提取图片并写入图谱。
    任务已在运行时返回 409。
    """
    from ..services.backfill_service import start_backfill, get_backfill_status
    status = get_backfill_status()
    if status["status"] == "running":
        raise HTTPException(409, "补全任务已在运行中")
    result = await start_backfill()
    return result


@router.post("/documents/backfill/pause", summary="暂停图片补全任务")
async def backfill_pause(_admin=Depends(get_admin_user)):
    """设置暂停标志，当前文档处理完后进入等待状态。"""
    from ..services.backfill_service import pause_backfill, get_backfill_status
    result = pause_backfill()
    if not result["ok"]:
        raise HTTPException(400, result["reason"])
    return {**result, "progress": get_backfill_status()}


@router.post("/documents/backfill/resume", summary="恢复图片补全任务")
async def backfill_resume(_admin=Depends(get_admin_user)):
    """删除暂停标志，继续处理剩余文档。"""
    from ..services.backfill_service import resume_backfill, get_backfill_status
    result = resume_backfill()
    return {**result, "progress": get_backfill_status()}


@router.get("/documents/backfill/status", summary="查询图片补全进度")
async def backfill_status(_user=Depends(get_current_user)):
    """
    返回补全任务当前状态（所有已登录用户可查询）：
    - status: idle / running / paused / completed
    - total / done / percent
    - current_doc：正在处理的文档
    - elapsed_seconds / estimated_remaining_seconds
    """
    from ..services.backfill_service import get_backfill_status
    return get_backfill_status()


@router.post("/documents/backfill/stop", summary="停止图片补全任务")
async def backfill_stop(_admin=Depends(get_admin_user)):
    """停止任务并清除所有进度数据，状态归 idle。"""
    from ..services.backfill_service import stop_backfill
    result = stop_backfill()
    if not result["ok"]:
        raise HTTPException(400, result["reason"])
    return result
