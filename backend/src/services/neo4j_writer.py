import logging
from ..core.database import get_driver
from ..models.schemas import DocumentSchema
from .embedder import embed_texts
from .milvus_store import upsert_sections
from .es_store import index_sections

logger = logging.getLogger(__name__)

def write_document(doc: DocumentSchema) -> None:
    # 把解析好的文档写入 Neo4j
    driver = get_driver()

    with driver.session() as session:
        # 第一条请求：写入 Document 节点
        session.run(
            """
            MERGE (d: Document {name: $doc_id})
            SET d.version = $version,
                d.title   = $title,
                d.issue_date = $issue_date,
                d.doc_type   = 'CPS'
            """,
            doc_id=doc.doc_id,
            version=doc.version,
            title=doc.title,
            issue_date=doc.issue_date,
        )

        logger.info("写入 Document 节点 doc_id=%s", doc.doc_id)
        # 第二条请求：批量写入所有 Section 节点并建立关系
        # 写入向量到 Milvus
        texts = [f"{s.title}\n{s.content}" for s in doc.sections]
        embeddings = embed_texts(texts)

        milvus_data = [
            {
                "chunk_id":  s.chunk_id,
                "doc_id":    doc.doc_id,
                "text":      f"{s.title}\n{s.content}",
                "embedding": embeddings[i],
            }
            for i, s in enumerate(doc.sections)
        ]
        upsert_sections(milvus_data)
        logger.info("写入 Milvus 向量 doc_id=%s sections=%d", doc.doc_id, len(doc.sections))

        sections_data = [
            {
                "chunk_id":  s.chunk_id,
                "number":    s.number,
                "title":     s.title,
                "content":   s.content,
                # "embedding": embeddings[i],
            }
            for i, s in enumerate(doc.sections)
        ]

        session.run("""
            MATCH (d:Document {name: $doc_id})
            UNWIND $sections AS s
            MERGE (sec:Section {chunk_id: s.chunk_id})
            SET sec.doc_id         = $doc_id,
                sec.number         = s.number,
                sec.section_number = s.number,
                sec.title          = s.title,
                sec.content        = s.content
            MERGE (d)-[:HAS_SECTION]->(sec)
        """,
        doc_id=doc.doc_id,
        sections=sections_data,
        )

        # 第三条请求：写入引用关系
        if doc.refs:
            session.run(
                """
                MATCH (d: Document {name: $doc_id})
                UNWIND $refs AS ref_id
                MERGE (ref: Document {name: ref_id})
                MERGE (d)-[:REFERENCES]->(ref)
                """,
                doc_id=doc.doc_id,
                refs=doc.refs,
            )
            logger.info("写入引用关系 %s -> %s", doc.doc_id, doc.refs)

        # 第四条请求：写入章节层级关系（HAS_SUBSECTION）和顺序关系（NEXT_SECTION）
        number_to_chunk = {s.number: s.chunk_id for s in doc.sections}

        parent_pairs = []
        for s in doc.sections:
            parts = s.number.split(".")
            if len(parts) > 1:
                parent_number = ".".join(parts[:-1])
                if parent_number in number_to_chunk:
                    parent_pairs.append({
                        "parent_id": number_to_chunk[parent_number],
                        "child_id":  s.chunk_id,
                    })

        if parent_pairs:
            session.run(
                """
                UNWIND $pairs AS p
                MATCH (parent:Section {chunk_id: p.parent_id})
                MATCH (child:Section  {chunk_id: p.child_id})
                MERGE (parent)-[:HAS_SUBSECTION]->(child)
                """,
                pairs=parent_pairs,
            )
            logger.info("写入层级关系 %d 条", len(parent_pairs))

        next_pairs = [
            {"from_id": doc.sections[i].chunk_id, "to_id": doc.sections[i + 1].chunk_id}
            for i in range(len(doc.sections) - 1)
        ]
        if next_pairs:
            session.run(
                """
                UNWIND $pairs AS p
                MATCH (a:Section {chunk_id: p.from_id})
                MATCH (b:Section {chunk_id: p.to_id})
                MERGE (a)-[:NEXT_SECTION]->(b)
                """,
                pairs=next_pairs,
            )
            logger.info("写入顺序关系 %d 条", len(next_pairs))

        # 写入 ES
        es_data = [
            {
                "chunk_id": s.chunk_id,
                "doc_id":   doc.doc_id,
                "number":   s.number,
                "title":    s.title,
                "content":  s.content,
            }
            for s in doc.sections
        ]
        index_sections(es_data)
        logger.info("写入 ES doc_id=%s sections=%d", doc.doc_id, len(doc.sections))

        # ── 版本溯源 ────────────────────────────────────────────────────────
        # 规则：doc_id 末位若为字母（A/B/C…），则视为同一规范的不同版次
        # 例：CPS1220A SUPERSEDES CPS1220（无版次）或 CPS1220_prev
        _link_version_lineage(session, doc.doc_id, doc.version or "")

    logger.info("写入完成 doc_id=%s sections=%d", doc.doc_id, len(doc.sections))


def _link_version_lineage(session, doc_id: str, version: str) -> None:
    """
    建立版本溯源关系 SUPERSEDES / OBSOLETED_BY。

    策略：
    1. 若 doc_id 末位是字母（如 CPS1220B），则 base = CPS1220；
       查找所有 base 匹配且版本低于当前的 Document，建立 (new)-[:SUPERSEDES]->(old)。
    2. 若 version 字段存在（如 version="B"），也用 version 字段比较。
    同时检测新增章节（ADDED_SECTION）和删除章节（REMOVED_SECTION）。
    """
    import re

    # 尝试从 doc_id 末位提取版本字母，如 CPS1220B → base=CPS1220, ver_letter=B
    m = re.match(r'^(.+?)([A-Z])$', doc_id)
    if m:
        base, ver_letter = m.group(1), m.group(2)
    else:
        # 无版本字母后缀，用 version 字段
        base = doc_id
        ver_letter = version[:1].upper() if version else ""

    if not ver_letter:
        return  # 无法确定版次，跳过

    # 查找同 base 的旧版本（版次字母 < 当前）
    result = session.run("""
        MATCH (old:Document)
        WHERE old.name STARTS WITH $base
          AND old.name <> $doc_id
          AND (
            (old.name =~ $ver_pattern AND substring(old.name, size($base), 1) < $ver_letter)
            OR
            (old.version IS NOT NULL AND old.version < $ver_letter AND old.name = $base)
          )
        RETURN old.name AS old_id
    """, base=base, doc_id=doc_id, ver_pattern=f"^{re.escape(base)}[A-Z]$",
         ver_letter=ver_letter)

    old_ids = [r["old_id"] for r in result]
    if not old_ids:
        return

    for old_id in old_ids:
        session.run("""
            MATCH (new_doc:Document {name: $new_id})
            MATCH (old_doc:Document {name: $old_id})
            MERGE (new_doc)-[:SUPERSEDES]->(old_doc)
            MERGE (old_doc)-[:OBSOLETED_BY]->(new_doc)
        """, new_id=doc_id, old_id=old_id)
        logger.info("版本溯源: %s SUPERSEDES %s", doc_id, old_id)

        # ── 章节级变更检测 ───────────────────────────────────────────────
        # 新版本有、旧版本无的章节 → ADDED_SECTION
        session.run("""
            MATCH (new_doc:Document {name: $new_id})-[:HAS_SECTION]->(new_sec:Section)
            WHERE NOT EXISTS {
                MATCH (old_doc:Document {name: $old_id})-[:HAS_SECTION]->(old_sec:Section)
                WHERE old_sec.number = new_sec.number
            }
            MERGE (new_doc)-[:ADDED_SECTION]->(new_sec)
        """, new_id=doc_id, old_id=old_id)

        # 旧版本有、新版本无的章节 → REMOVED_SECTION
        session.run("""
            MATCH (old_doc:Document {name: $old_id})-[:HAS_SECTION]->(old_sec:Section)
            WHERE NOT EXISTS {
                MATCH (new_doc:Document {name: $new_id})-[:HAS_SECTION]->(new_sec:Section)
                WHERE new_sec.number = old_sec.number
            }
            MERGE (old_doc)-[:REMOVED_SECTION]->(old_sec)
        """, new_id=doc_id, old_id=old_id)

        # 内容发生变化的章节 → CHANGED_SECTION（旧→新）
        session.run("""
            MATCH (new_doc:Document {name: $new_id})-[:HAS_SECTION]->(new_sec:Section)
            MATCH (old_doc:Document {name: $old_id})-[:HAS_SECTION]->(old_sec:Section)
            WHERE new_sec.number = old_sec.number
              AND new_sec.content <> old_sec.content
            MERGE (old_sec)-[:CHANGED_TO]->(new_sec)
        """, new_id=doc_id, old_id=old_id)

        logger.info("章节变更检测完成: %s → %s", old_id, doc_id)
