import logging
import tempfile
import asyncio
import subprocess
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, Response
from neo4j import Driver
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.database import get_driver
from ..db.session import get_db
from ..db.models import AuditLog, User
from ..auth.deps import get_optional_user, get_admin_user
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
            pdf_bytes = await asyncio.to_thread(download_bytes, BUCKET_RAW_DOCUMENTS, storage_key)
            return _pdf_response(pdf_bytes, doc_id)

        # DOCX/DOC：优先从 previews/ 桶返回缓存
        preview_key = f"{doc_id}.pdf"
        if await asyncio.to_thread(object_exists, BUCKET_PREVIEWS, preview_key):
            pdf_bytes = await asyncio.to_thread(download_bytes, BUCKET_PREVIEWS, preview_key)
            return _pdf_response(pdf_bytes, doc_id)

        # 缓存未命中：下载原文 → LibreOffice 转 PDF → 上传缓存 → 返回
        raw_bytes = await asyncio.to_thread(download_bytes, BUCKET_RAW_DOCUMENTS, storage_key)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(raw_bytes)
            tmp_path = Path(tmp.name)
        try:
            pdf_path = await asyncio.to_thread(_convert_to_pdf, tmp_path)
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
            src = await asyncio.to_thread(_convert_to_pdf, src)

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
        try:
            raw_bytes = await asyncio.to_thread(
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
