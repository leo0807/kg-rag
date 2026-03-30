"""
src/services/semantic_linker.py
计算跨文档章节间的语义相似度，在 Neo4j 中建立 SIMILAR_TO 边。

关系：(Section)-[:SIMILAR_TO {score: 0.92}]->(Section)
  - 只在不同 doc_id 的章节之间建立
  - 相似度 >= threshold 才写入

用法（主动触发，离线批处理）：
    from src.services.semantic_linker import build_semantic_links
    build_semantic_links(driver, threshold=0.88, top_k=5)
"""
import logging
import numpy as np
from neo4j import Driver

logger = logging.getLogger(__name__)


def _cosine_matrix(mat: np.ndarray) -> np.ndarray:
    """返回归一化后的余弦相似度矩阵 (n x n)"""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    normed = mat / norms
    return normed @ normed.T


def build_semantic_links(
    driver: Driver,
    threshold: float = 0.88,
    top_k: int = 5,
    dry_run: bool = False,
) -> dict:
    """
    拉取所有 Section 节点的 embedding，计算跨文档相似度，写入 SIMILAR_TO 边。

    Args:
        threshold: 余弦相似度阈值，低于此值不写边
        top_k:     每个章节最多写 top_k 条跨文档相似边
        dry_run:   True 时只统计，不写入 Neo4j

    Returns:
        {"sections": n, "pairs": written, "skipped": below_threshold}
    """
    # ── 1. 从 Milvus 拉取所有 Section embedding ──────────────────────────────
    try:
        from .milvus_store import get_all_embeddings
        rows = get_all_embeddings()          # [{"chunk_id", "doc_id", "embedding"}]
    except Exception as e:
        logger.error("从 Milvus 拉取 embedding 失败: %s", e)
        return {"error": str(e)}

    if len(rows) < 2:
        logger.info("Section 数量不足，跳过语义链接")
        return {"sections": len(rows), "pairs": 0, "skipped": 0}

    chunk_ids = [r["chunk_id"] for r in rows]
    doc_ids   = [r["doc_id"]   for r in rows]
    mat       = np.array([r["embedding"] for r in rows], dtype=np.float32)

    logger.info("开始计算语义相似度 sections=%d", len(rows))

    # ── 2. 计算相似度矩阵 ────────────────────────────────────────────────────
    sim_matrix = _cosine_matrix(mat)          # (n x n) float32
    np.fill_diagonal(sim_matrix, 0.0)        # 排除自身

    # ── 3. 筛选跨文档、高相似度 pair ─────────────────────────────────────────
    pairs_to_write = []
    skipped = 0
    n = len(rows)

    for i in range(n):
        sims = sim_matrix[i].copy()
        # 屏蔽同文档章节
        for j in range(n):
            if doc_ids[j] == doc_ids[i]:
                sims[j] = 0.0

        # 取 top_k
        top_indices = np.argsort(sims)[::-1][:top_k]
        for j in top_indices:
            score = float(sims[j])
            if score < threshold:
                skipped += 1
                continue
            # 去重：只写 i < j 方向（双向关系在 Cypher 里用无向 MERGE）
            if i < j:
                pairs_to_write.append({
                    "src":   chunk_ids[i],
                    "dst":   chunk_ids[j],
                    "score": round(score, 4),
                })

    logger.info("筛选完成 pairs=%d skipped=%d (threshold=%.2f)", len(pairs_to_write), skipped, threshold)

    if dry_run or not pairs_to_write:
        return {"sections": n, "pairs": len(pairs_to_write), "skipped": skipped, "dry_run": dry_run}

    # ── 4. 批量写入 Neo4j ────────────────────────────────────────────────────
    batch_size = 200
    written = 0
    with driver.session() as session:
        for start in range(0, len(pairs_to_write), batch_size):
            batch = pairs_to_write[start: start + batch_size]
            session.run("""
                UNWIND $pairs AS p
                MATCH (a:Section {chunk_id: p.src})
                MATCH (b:Section {chunk_id: p.dst})
                MERGE (a)-[r:SIMILAR_TO]-(b)
                SET r.score = p.score
            """, pairs=batch)
            written += len(batch)

    logger.info("SIMILAR_TO 边写入完成 pairs=%d", written)
    return {"sections": n, "pairs": written, "skipped": skipped}
