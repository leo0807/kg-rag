import logging
from ..core.database import get_driver
from ..core.config import settings
from .embedder import embed_texts

logger = logging.getLogger(__name__)

# 这条 Cypher 完成三件事：
#   1. 向量召回：db.index.vector.queryNodes 在 section_embedding 索引上做 ANN 搜索
#   2. 取文档元数据：MATCH (d:Document)-[:HAS_SECTION]->(sec)
#   3. 图谱增强：
#      - OPTIONAL MATCH parent：沿 HAS_SUBSECTION 反向找父章节，提供大纲级别的上下文
#      - OPTIONAL MATCH prev/next：沿 NEXT_SECTION 取前后相邻章节，避免内容被截断
_RETRIEVE_CYPHER = """
CALL db.index.vector.queryNodes('section_embedding', $top_k, $embedding)
YIELD node AS sec, score
MATCH (d:Document)-[:HAS_SECTION]->(sec)
OPTIONAL MATCH (parent:Section)-[:HAS_SUBSECTION]->(sec)
OPTIONAL MATCH (prev:Section)-[:NEXT_SECTION]->(sec)
OPTIONAL MATCH (sec)-[:NEXT_SECTION]->(nxt:Section)
RETURN
    sec.chunk_id    AS chunk_id,
    sec.number      AS number,
    sec.title       AS title,
    sec.content     AS content,
    d.name          AS doc_id,
    d.title         AS doc_title,
    parent.title    AS parent_title,
    parent.content  AS parent_content,
    prev.content    AS prev_content,
    nxt.content     AS next_content,
    score
ORDER BY score DESC
"""

def retrieve(question: str) -> list[dict]:
    """
    把问题向量化，在 Neo4j 中向量召回 top-K 章节，
    并通过图遍历附加父章节和相邻章节的文本。
    返回一个 list，每个元素对应一个召回片段及其图谱上下文。
    """
    # 问题嵌入：维度与 Section.embedding 一致（1024）
    embedding = embed_texts([question])[0]

    driver = get_driver()
    with driver.session() as session:
        result = session.run(
            _RETRIEVE_CYPHER,
            embedding=embedding,
            top_k=settings.RETRIEVER_TOP_K,
        )
        records = [dict(r) for r in result]

    logger.info("向量召回 %d 条，问题：%s", len(records), question[:30])
    return records


def build_context(records: list[dict]) -> str:
    """
    把召回结果拼装成一段给 LLM 的上下文字符串。

    拼装策略：
    - 如果有父章节：先放父章节标题，让 LLM 知道所在位置
    - 如果有前一章节：加一小段前文，避免内容突然开始
    - 核心内容：命中章节自身
    - 如果有后一章节：加一小段后文，避免内容突然结束
    - 每个片段之间用分割线隔开，方便 LLM 区分来源
    """
    parts = []
    for i, rec in enumerate(records):
        lines = [f"【片段 {i + 1}】来源：{rec['doc_id']} § {rec['number']} {rec['title']}"]

        if rec.get("parent_title"):
            lines.append(f"[上级章节: {rec['parent_title']}]")

        if rec.get("prev_content"):
            # 只取前一节末尾 200 字，避免 context 过长
            lines.append("[前文节选]\n" + rec["prev_content"][-200:])

        lines.append("[正文]\n" + rec["content"])

        if rec.get("next_content"):
            # 只取后一节开头 200 字
            lines.append("[后文节选]\n" + rec["next_content"][:200])

        parts.append("\n".join(lines))

    return "\n\n---\n\n".join(parts)
