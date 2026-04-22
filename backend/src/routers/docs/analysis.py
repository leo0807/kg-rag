import logging
import difflib
from fastapi import APIRouter, Depends, HTTPException
from neo4j import Driver
from ...core.database import get_driver
from ...auth.deps import get_admin_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["documents"])

@router.get("/documents/{doc_id}/validate")
async def validate_document(
    doc_id: str,
    driver: Driver = Depends(get_driver),
    _admin = Depends(get_admin_user),
):
    """验证单个文档的解析质量，返回结构化报告。"""
    from ...services.parsing.validator import validate_document as _validate
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
    from ...services.parsing.validator import validate_all as _validate_all
    return _validate_all(driver)


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
