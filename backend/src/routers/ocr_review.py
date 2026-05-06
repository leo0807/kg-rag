"""OCR 纠错 / 多模态手动补全 — 人工审核待完善内容"""
from __future__ import annotations
import asyncio, csv, io, logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from neo4j import Driver
from ..core.database import get_driver
from ..auth.deps import get_admin_user
from ..db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/annotation", tags=["ocr-review"])

# ── 乱码检测 ──────────────────────────────────────────────────────────────────
_JUNK = set("□■◆▲▽※○●◇◈�")

def _confidence(content: str) -> float:
    if not content:
        return 0.0
    junk = sum(1 for c in content if c in _JUNK or ('─' <= c <= '◿') or (ord(c) < 0x20 and c not in '\n\t\r'))
    return round(max(0.0, 1.0 - (junk / max(len(content), 1)) * 10), 2)


def _fetch_pending(driver: Driver) -> dict:
    with driver.session() as s:
        sec_rows = s.run("""
            MATCH (sec:Section)
            WHERE sec.content IS NOT NULL AND size(sec.content) > 0
            RETURN sec.chunk_id AS chunk_id, sec.title AS title,
                   sec.content AS content, sec.doc_id AS doc_id
            LIMIT 500
        """)
        sections_raw = [dict(r) for r in sec_rows]

        img_rows = s.run("""
            MATCH (i:Image)
            WHERE coalesce(i.caption, '') = '' OR coalesce(i.analysis_level, 'none') = 'basic'
            RETURN i.image_id AS image_id, i.minio_path AS minio_path,
                   i.page_num AS page_num, i.doc_id AS doc_id,
                   coalesce(i.caption, '') AS current_caption,
                   coalesce(i.analysis_level, 'none') AS analysis_level
            LIMIT 200
        """)
        images = [dict(r) for r in img_rows]

    pending_sections = []
    for sec in sections_raw:
        conf = _confidence(sec["content"] or "")
        if conf < 0.85:
            pending_sections.append({
                "chunk_id":   sec["chunk_id"],
                "title":      sec["title"] or "",
                "content":    (sec["content"] or "")[:500],
                "confidence": conf,
                "doc_id":     sec["doc_id"] or "",
            })

    for img in images:
        iid = img["image_id"] or ""
        img["url"] = f"/api/images/{iid}" if iid else None

    return {
        "pending_sections": pending_sections[:100],
        "pending_images":   images,
        "total_pending":    len(pending_sections) + len(images),
    }


@router.get("/pending")
async def get_pending(driver: Driver = Depends(get_driver), _: User = Depends(get_admin_user)):
    return await asyncio.to_thread(_fetch_pending, driver)


# ── 章节修正 ──────────────────────────────────────────────────────────────────
class SectionPatch(BaseModel):
    title:   str | None = None
    content: str | None = None


@router.patch("/sections/{chunk_id}")
async def patch_section(chunk_id: str, req: SectionPatch, driver: Driver = Depends(get_driver), _: User = Depends(get_admin_user)):
    updates = {k: v for k, v in {"title": req.title, "content": req.content}.items() if v is not None}
    if not updates:
        return {"status": "OK", "updated": 0}
    set_clause = ", ".join(f"s.`{k}` = ${k}" for k in updates)

    def _run():
        with driver.session() as s:
            rec = s.run(f"MATCH (s:Section {{chunk_id: $cid}}) SET {set_clause} RETURN count(s) AS cnt",
                        cid=chunk_id, **updates).single()
            return rec["cnt"] if rec else 0

    cnt = await asyncio.to_thread(_run)
    return {"status": "OK", "updated": cnt}


# ── 图片修正 ──────────────────────────────────────────────────────────────────
class ImagePatch(BaseModel):
    caption:    str | None = None
    is_drawing: bool | None = None


@router.patch("/images/{image_id}")
async def patch_image(image_id: str, req: ImagePatch, driver: Driver = Depends(get_driver), _: User = Depends(get_admin_user)):
    updates = {k: v for k, v in {"caption": req.caption, "is_drawing": req.is_drawing}.items() if v is not None}
    if not updates:
        return {"status": "OK", "updated": 0}
    set_clause = ", ".join(f"i.`{k}` = ${k}" for k in updates)

    def _run():
        with driver.session() as s:
            rec = s.run(f"MATCH (i:Image {{image_id: $iid}}) SET {set_clause}, i.analysis_level = 'manual' RETURN count(i) AS cnt",
                        iid=image_id, **updates).single()
            return rec["cnt"] if rec else 0

    cnt = await asyncio.to_thread(_run)
    return {"status": "OK", "updated": cnt}


# ── VLM 重新分析 ──────────────────────────────────────────────────────────────
@router.post("/images/{image_id}/analyze")
async def reanalyze_image(image_id: str, driver: Driver = Depends(get_driver), _: User = Depends(get_admin_user)):
    with driver.session() as s:
        rec = s.run("MATCH (i:Image {image_id: $iid}) RETURN i.path AS path, i.minio_path AS mp, i.caption AS cap, i.doc_id AS doc_id LIMIT 1",
                    iid=image_id).single()
    if not rec:
        from fastapi import HTTPException
        raise HTTPException(404, f"图片不存在: {image_id}")

    async def _run_vlm():
        try:
            from ..routers.docs.images import resolve_image_binary_path
            from ..services.images.drawing_analyzer import analyze_drawing
            image_path, cleanup = resolve_image_binary_path(image_id=image_id, local_path=rec["path"], minio_path=rec["mp"])
            result = analyze_drawing(str(image_path), rec["cap"] or "", rec["doc_id"] or "")
            import json as _json
            with driver.session() as s:
                s.run("MATCH (i:Image {image_id: $iid}) SET i.is_drawing=$d, i.caption=$c, i.analysis_level='full'",
                      iid=image_id, d=result.get("is_drawing", False), c=result.get("summary", ""))
            if cleanup:
                cleanup.unlink(missing_ok=True)
        except Exception as e:
            logger.warning("VLM reanalyze failed %s: %s", image_id, e)

    asyncio.create_task(_run_vlm())
    return {"status": "analyzing", "image_id": image_id}


# ── 批量 VLM 分析 ─────────────────────────────────────────────────────────────
@router.post("/batch-analyze")
async def batch_analyze(driver: Driver = Depends(get_driver), _: User = Depends(get_admin_user)):
    def _fetch():
        with driver.session() as s:
            rows = s.run("MATCH (i:Image) WHERE coalesce(i.caption,'')='' RETURN i.image_id AS iid, i.path AS path, i.minio_path AS mp, i.doc_id AS doc_id LIMIT 50")
            return [dict(r) for r in rows]

    images = await asyncio.to_thread(_fetch)

    async def _run_all():
        from ..routers.docs.images import resolve_image_binary_path
        from ..services.images.drawing_analyzer import analyze_drawing
        for img in images:
            iid = img["iid"]
            try:
                image_path, cleanup = resolve_image_binary_path(image_id=iid, local_path=img["path"], minio_path=img["mp"])
                result = await asyncio.to_thread(analyze_drawing, str(image_path), "", img["doc_id"] or "")
                with driver.session() as s:
                    s.run("MATCH (i:Image {image_id:$iid}) SET i.is_drawing=$d,i.caption=$c,i.analysis_level='full'",
                          iid=iid, d=result.get("is_drawing", False), c=result.get("summary", ""))
                if cleanup:
                    cleanup.unlink(missing_ok=True)
            except Exception as e:
                logger.warning("batch analyze failed %s: %s", iid, e)

    asyncio.create_task(_run_all())
    return {"status": "started", "count": len(images)}


# ── CSV 导出 ──────────────────────────────────────────────────────────────────
@router.get("/export-csv")
async def export_csv(driver: Driver = Depends(get_driver), _: User = Depends(get_admin_user)):
    pending = await asyncio.to_thread(_fetch_pending, driver)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["type", "id", "doc_id", "title/page", "content/caption", "confidence"])
    for s in pending["pending_sections"]:
        w.writerow(["section", s["chunk_id"], s["doc_id"], s["title"], s["content"][:200], s["confidence"]])
    for img in pending["pending_images"]:
        w.writerow(["image", img["image_id"], img["doc_id"], f"page {img.get('page_num','?')}", img["current_caption"], img["analysis_level"]])
    buf.seek(0)
    return StreamingResponse(io.BytesIO(buf.getvalue().encode("utf-8-sig")),
                             media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=\"pending_review.csv\""})
