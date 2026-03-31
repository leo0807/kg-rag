#!/usr/bin/env python3
"""
train_gnn.py — GraphSAGE 离线训练脚本

功能流程:
  1. 从 Neo4j 拉取所有 Section 节点及结构特征
  2. 从 Milvus 拉取对应 BGE-M3 文本嵌入
  3. 构建 Section-Section 邻接矩阵（结构链接 + 实体共享 + SIMILAR_TO）
  4. 以「同文档章节」为正样本对，用 InfoNCE 损失训练 GraphSAGE
  5. 推断所有节点的 GNN 嵌入，保存至 backend/models/gnn/

用法:
  cd /path/to/kg-rag
  python -m backend.scripts.train_gnn [--epochs 100] [--lr 1e-3] [--device cpu]
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.optim import Adam

# ── 路径设置 ──────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.src.core.config import settings
from backend.src.models.graphsage import GraphSAGE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("train_gnn")

GNN_DIR   = ROOT / "backend" / "models" / "gnn"
GNN_DIR.mkdir(parents=True, exist_ok=True)

# 输出维度与 BGE-M3 保持一致，使查询向量可直接检索 GNN 嵌入
OUT_DIM    = 1024
HIDDEN_DIM = 512
STRUCT_DIM = 16   # 结构特征维度（补零至 16）


# ────────────────────────────────────────────────────────────
# 数据拉取
# ────────────────────────────────────────────────────────────

def fetch_sections(driver) -> list[dict]:
    """从 Neo4j 获取所有 Section 及其结构统计特征"""
    with driver.session() as s:
        rows = s.run("""
            MATCH (sec:Section)
            OPTIONAL MATCH (d:Document)-[:HAS_SECTION]->(sec)
            OPTIONAL MATCH (sec)-[:REQUIRES_TOOL]->(t:Tool)
            OPTIONAL MATCH (sec)-[:USES_MATERIAL]->(m:Material)
            OPTIONAL MATCH (sec)-[:INVOLVES_PROCESS]->(p:Process)
            OPTIONAL MATCH (sec)-[:HAS_CONSTRAINT]->(c:Constraint)
            OPTIONAL MATCH (sec)-[:HAS_IMAGE]->(img:Image)
            OPTIONAL MATCH (sec)-[:HAS_SUBSECTION]->(sub:Section)
            WITH sec,
                 d.doc_type                AS doc_type,
                 count(DISTINCT t)          AS num_tools,
                 count(DISTINCT m)          AS num_materials,
                 count(DISTINCT p)          AS num_processes,
                 count(DISTINCT c)          AS num_constraints,
                 count(DISTINCT img)        AS num_images,
                 count(DISTINCT sub)        AS num_subsections
            RETURN sec.chunk_id AS chunk_id,
                   sec.doc_id   AS doc_id,
                   doc_type,
                   num_tools, num_materials, num_processes,
                   num_constraints, num_images, num_subsections
        """)
        sections = [dict(r) for r in rows]
    logger.info("Neo4j 返回 %d 个章节", len(sections))
    return sections


def fetch_text_embeddings() -> dict[str, list[float]]:
    """从 Milvus 拉取所有章节的 BGE-M3 文本嵌入"""
    emb_map: dict[str, list[float]] = {}
    try:
        from backend.src.services.milvus_store import connect_milvus, get_all_embeddings
        connect_milvus(host=settings.MILVUS_HOST, port=str(settings.MILVUS_PORT))
        for item in get_all_embeddings():
            emb_map[item["chunk_id"]] = item["embedding"]
        logger.info("Milvus 返回 %d 条文本嵌入", len(emb_map))
    except Exception as e:
        logger.warning("Milvus 不可用，将对所有节点使用零文本嵌入: %s", e)
    return emb_map


def fetch_edges(driver, chunk_id_set: set[str]) -> list[tuple[str, str]]:
    """
    构建 Section-Section 邻接边（无向）:
      - HAS_SUBSECTION / NEXT_SECTION（结构链接）
      - 共享 Tool/Material/Process 的章节对（实体共享）
      - SIMILAR_TO（语义相似）
    """
    edges: set[tuple[str, str]] = set()

    def add(src: str, dst: str):
        if src in chunk_id_set and dst in chunk_id_set and src != dst:
            a, b = (src, dst) if src < dst else (dst, src)
            edges.add((a, b))

    with driver.session() as s:
        # 结构链接
        for r in s.run("""
            MATCH (a:Section)-[:HAS_SUBSECTION|NEXT_SECTION]-(b:Section)
            RETURN a.chunk_id AS src, b.chunk_id AS dst
        """):
            add(r["src"], r["dst"])

        # 实体共享（限制数量防止爆炸）
        for r in s.run("""
            MATCH (a:Section)-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]->(e)
                  <-[:REQUIRES_TOOL|USES_MATERIAL|INVOLVES_PROCESS]-(b:Section)
            WHERE a.chunk_id < b.chunk_id
            RETURN a.chunk_id AS src, b.chunk_id AS dst
            LIMIT 200000
        """):
            add(r["src"], r["dst"])

        # 语义相似边
        for r in s.run("""
            MATCH (a:Section)-[:SIMILAR_TO]-(b:Section)
            RETURN a.chunk_id AS src, b.chunk_id AS dst
        """):
            add(r["src"], r["dst"])

    edge_list = [(a, b) for a, b in edges]
    logger.info("邻接边: %d 条（去重后）", len(edge_list))
    return edge_list


def fetch_positive_pairs(driver, chunk_id_set: set[str]) -> list[tuple[str, str]]:
    """
    构建训练正样本对:
      - 同一文档中相邻章节（同文档 + 位置相近）
      - SIMILAR_TO 边（显式语义相似对）
    """
    pairs: list[tuple[str, str]] = []

    with driver.session() as s:
        # 同文档章节对
        for rec in s.run("""
            MATCH (d:Document)-[:HAS_SECTION]->(sec:Section)
            WITH d, collect(sec.chunk_id) AS secs
            WHERE size(secs) > 1
            RETURN secs
        """):
            secs = [cid for cid in rec["secs"] if cid in chunk_id_set]
            # 取相邻 ±3 以内的章节对（过于稀疏的正对对训练无益）
            for i in range(len(secs)):
                for j in range(i + 1, min(i + 4, len(secs))):
                    pairs.append((secs[i], secs[j]))

        # SIMILAR_TO 正对
        for r in s.run("""
            MATCH (a:Section)-[:SIMILAR_TO]-(b:Section)
            WHERE a.chunk_id < b.chunk_id
            RETURN a.chunk_id AS src, b.chunk_id AS dst
        """):
            if r["src"] in chunk_id_set and r["dst"] in chunk_id_set:
                pairs.append((r["src"], r["dst"]))

    logger.info("正样本对: %d 对", len(pairs))
    return pairs


# ────────────────────────────────────────────────────────────
# 特征工程
# ────────────────────────────────────────────────────────────

_DOC_TYPES = ["engineering", "standard", "manual", "other"]


def build_struct_features(sections: list[dict]) -> np.ndarray:
    """
    构建结构特征矩阵 [N, STRUCT_DIM]:
      列 0-5:  num_tools/materials/processes/constraints/images/subsections (归一化)
      列 6-9:  doc_type one-hot (engineering/standard/manual/other)
      列 10-15: 保留（零填充）
    """
    raw = np.zeros((len(sections), STRUCT_DIM), dtype=np.float32)
    for i, s in enumerate(sections):
        raw[i, 0] = float(s.get("num_tools",        0) or 0)
        raw[i, 1] = float(s.get("num_materials",     0) or 0)
        raw[i, 2] = float(s.get("num_processes",     0) or 0)
        raw[i, 3] = float(s.get("num_constraints",   0) or 0)
        raw[i, 4] = float(s.get("num_images",        0) or 0)
        raw[i, 5] = float(s.get("num_subsections",   0) or 0)
        dt = (s.get("doc_type") or "other").lower()
        k  = _DOC_TYPES.index(dt) if dt in _DOC_TYPES else 3
        raw[i, 6 + k] = 1.0

    # Min-max 归一化数值列（列 0-5）
    col_max = raw[:, :6].max(axis=0, keepdims=True).clip(min=1)
    raw[:, :6] /= col_max
    return raw


# ────────────────────────────────────────────────────────────
# 图工具
# ────────────────────────────────────────────────────────────

def build_sparse_adj(n: int, edges_idx: list[tuple[int, int]]) -> torch.Tensor:
    """构建对称稀疏邻接矩阵（含自环），返回 COO sparse tensor"""
    rows, cols = [], []
    for a, b in edges_idx:
        rows += [a, b]
        cols += [b, a]
    # 自环
    rows += list(range(n))
    cols += list(range(n))

    indices = torch.tensor([rows, cols], dtype=torch.long)
    values  = torch.ones(len(rows), dtype=torch.float32)
    adj     = torch.sparse_coo_tensor(indices, values, size=(n, n))
    return adj.coalesce()


# ────────────────────────────────────────────────────────────
# 损失函数
# ────────────────────────────────────────────────────────────

def info_nce_loss(
    anchor: torch.Tensor,
    positive: torch.Tensor,
    temperature: float = 0.07,
) -> torch.Tensor:
    """
    InfoNCE（NT-Xent）对比损失，使用 batch 内负样本。
    anchor / positive: [B, D], 均已 L2 归一化
    """
    sim = torch.mm(anchor, positive.t()) / temperature   # [B, B]
    labels = torch.arange(sim.size(0), device=sim.device)
    loss = (
        F.cross_entropy(sim,   labels) +
        F.cross_entropy(sim.t(), labels)
    ) / 2.0
    return loss


# ────────────────────────────────────────────────────────────
# 主训练流程
# ────────────────────────────────────────────────────────────

def train(args: argparse.Namespace):
    device = torch.device(args.device)
    logger.info("设备: %s", device)

    # ── 连接 Neo4j ──
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )

    # ── 1. 数据拉取 ──
    sections = fetch_sections(driver)
    if not sections:
        logger.error("Neo4j 中没有 Section 节点，请先导入文档后再训练")
        driver.close()
        return

    chunk_ids       = [s["chunk_id"] for s in sections]
    chunk_id_to_idx = {cid: i for i, cid in enumerate(chunk_ids)}
    chunk_id_set    = set(chunk_ids)
    N               = len(sections)

    text_emb_map = fetch_text_embeddings()

    # ── 2. 构建特征矩阵 ──
    text_matrix = np.zeros((N, 1024), dtype=np.float32)
    missing = 0
    for i, cid in enumerate(chunk_ids):
        emb = text_emb_map.get(cid)
        if emb is not None:
            text_matrix[i] = emb
        else:
            missing += 1
    if missing:
        logger.warning("%d 个章节缺少文本嵌入（将以零向量代替）", missing)

    struct_matrix = build_struct_features(sections)      # [N, 16]
    features      = np.concatenate([text_matrix, struct_matrix], axis=1)  # [N, 1040]
    feat_dim      = features.shape[1]
    logger.info("节点特征维度: %d (text=%d + struct=%d)", feat_dim, 1024, STRUCT_DIM)

    X = torch.tensor(features, dtype=torch.float32, device=device)

    # ── 3. 构建邻接矩阵 ──
    raw_edges  = fetch_edges(driver, chunk_id_set)
    edges_idx  = [
        (chunk_id_to_idx[a], chunk_id_to_idx[b])
        for a, b in raw_edges
        if a in chunk_id_to_idx and b in chunk_id_to_idx
    ]
    adj = build_sparse_adj(N, edges_idx).to(device)

    # ── 4. 正样本对 ──
    raw_pairs  = fetch_positive_pairs(driver, chunk_id_set)
    pair_idx   = torch.tensor(
        [(chunk_id_to_idx[a], chunk_id_to_idx[b])
         for a, b in raw_pairs
         if a in chunk_id_to_idx and b in chunk_id_to_idx],
        dtype=torch.long,
    )

    if len(pair_idx) == 0:
        logger.error("没有可用的正样本对，无法训练（请先导入多份文档）")
        driver.close()
        return

    # ── 5. 初始化模型 ──
    model = GraphSAGE(
        in_dim=feat_dim,
        hidden_dim=HIDDEN_DIM,
        out_dim=OUT_DIM,
        dropout=args.dropout,
    ).to(device)
    optimizer = Adam(model.parameters(), lr=args.lr, weight_decay=1e-5)

    logger.info(
        "开始训练 GraphSAGE | N=%d 节点, %d 边, %d 正对, epochs=%d, batch=%d",
        N, len(edges_idx), len(pair_idx), args.epochs, args.batch_size,
    )

    best_loss  = float("inf")
    patience_n = 0
    best_ckpt  = GNN_DIR / "model_best.pt"

    t0 = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        embeddings = model(X, adj)                       # [N, 1024]

        perm        = torch.randperm(len(pair_idx), device=device)[:args.batch_size]
        batch_pairs = pair_idx[perm.cpu()]               # index on CPU tensor
        anchors     = embeddings[batch_pairs[:, 0]]
        positives   = embeddings[batch_pairs[:, 1]]

        loss = info_nce_loss(anchors, positives, temperature=args.temperature)

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        if epoch % 10 == 0 or epoch == 1:
            logger.info(
                "Epoch %4d/%d | loss=%.4f | elapsed=%.1fs",
                epoch, args.epochs, loss.item(), time.time() - t0,
            )

        if loss.item() < best_loss - 1e-4:
            best_loss  = loss.item()
            patience_n = 0
            torch.save(model.state_dict(), best_ckpt)
        else:
            patience_n += 1
            if patience_n >= args.patience:
                logger.info("Early stopping at epoch %d (patience=%d)", epoch, args.patience)
                break

    # ── 6. 推断 GNN 嵌入 ──
    logger.info("加载最佳权重，推断全图 GNN 嵌入...")
    if best_ckpt.exists():
        model.load_state_dict(torch.load(best_ckpt, map_location=device))
    model.eval()
    with torch.no_grad():
        gnn_embs = model(X, adj).cpu().numpy()           # [N, 1024]

    # ── 7. 保存产物 ──
    np.save(GNN_DIR / "embeddings.npy", gnn_embs)

    with open(GNN_DIR / "chunk_ids.json", "w", encoding="utf-8") as f:
        json.dump(chunk_ids, f, ensure_ascii=False)

    metadata = {
        "trained_at":   int(time.time()),
        "num_nodes":    N,
        "num_edges":    len(edges_idx),
        "num_pairs":    len(pair_idx),
        "feat_dim":     feat_dim,
        "hidden_dim":   HIDDEN_DIM,
        "out_dim":      OUT_DIM,
        "best_loss":    float(best_loss),
        "epochs_run":   epoch,
    }
    with open(GNN_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info(
        "GNN 训练完成！嵌入已保存至 %s  [%d 节点 × %d 维]",
        GNN_DIR, N, OUT_DIM,
    )
    driver.close()


# ────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="训练 GraphSAGE GNN 嵌入")
    p.add_argument("--epochs",      type=int,   default=100)
    p.add_argument("--lr",          type=float, default=1e-3)
    p.add_argument("--batch_size",  type=int,   default=256)
    p.add_argument("--hidden_dim",  type=int,   default=HIDDEN_DIM)
    p.add_argument("--dropout",     type=float, default=0.2)
    p.add_argument("--temperature", type=float, default=0.07)
    p.add_argument("--patience",    type=int,   default=15)
    p.add_argument(
        "--device",
        type=str,
        default="cuda" if torch.cuda.is_available() else "cpu",
    )
    return p.parse_args()


if __name__ == "__main__":
    train(parse_args())
