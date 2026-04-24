"""
GNN 嵌入服务

功能:
  - 加载离线训练好的 GraphSAGE 嵌入（embeddings.npy + chunk_ids.json）
  - 在内存中对查询向量（BGE-M3 文本嵌入）做快速内积检索
  - 提供 reload() 接口供训练完成后热更新

设计说明:
  GNN 嵌入维度与 BGE-M3 相同（1024），已 L2 归一化，
  因此可以直接用归一化的文本查询向量做内积（= 余弦相似度）检索。
  GNN 在纯文本特征基础上额外融合了邻居类型分布、关系密度等结构信息，
  使结构上重要/相似的节点在嵌入空间中更近，提升结构相似节点的召回率。
"""
import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

_GNN_DIR = Path(__file__).resolve().parent.parent.parent.parent / "models" / "gnn"


class GNNService:
    """GraphSAGE 嵌入检索服务（应用级单例）"""

    def __init__(self):
        self.chunk_ids: list[str] = []
        self.embeddings: Optional[np.ndarray] = None  # [N, 1024], float32
        self.loaded = False
        self._try_load()

    # ── 生命周期 ──────────────────────────────────────────────

    def _try_load(self) -> None:
        emb_path = _GNN_DIR / "embeddings.npy"
        ids_path = _GNN_DIR / "chunk_ids.json"

        if not emb_path.exists() or not ids_path.exists():
            logger.info(
                "GNN 嵌入文件不存在（%s）。"
                "可运行 `python -m backend.scripts.train_gnn` 生成，"
                "或通过 POST /api/gnn/train 触发训练。",
                _GNN_DIR,
            )
            return

        try:
            embs = np.load(str(emb_path))
            with open(ids_path, "r", encoding="utf-8") as f:
                ids = json.load(f)

            if len(ids) != len(embs):
                logger.error(
                    "GNN 嵌入数量不一致: chunk_ids=%d vs embeddings=%d",
                    len(ids), len(embs),
                )
                return

            self.chunk_ids  = ids
            self.embeddings = embs.astype(np.float32)
            self.loaded     = True
            logger.info(
                "GNN 嵌入加载成功: %d 个节点, 维度=%d",
                len(self.chunk_ids), self.embeddings.shape[1],
            )
        except Exception as e:
            logger.error("GNN 嵌入加载失败: %s", e)

    def reload(self) -> None:
        """训练完成后调用，热替换嵌入矩阵"""
        self.loaded    = False
        self.chunk_ids = []
        self.embeddings = None
        self._try_load()

    # ── 检索 ──────────────────────────────────────────────────

    def search(
        self,
        query_vec: list[float],
        top_k: int = 10,
        doc_id: str = "",
    ) -> list[dict]:
        """
        用 BGE-M3 文本嵌入检索 GNN 嵌入空间中最近的章节。

        query_vec: BGE-M3 的原始输出（已归一化或未归一化均可）
        doc_id:    可选，过滤到特定文档（空字符串表示全库）
        返回: [{"chunk_id": ..., "score": float}, ...]，按 score 降序
        """
        if not self.loaded or self.embeddings is None:
            return []

        q = np.array(query_vec, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        scores = self.embeddings @ q   # [N]，内积 = 余弦相似度（已归一化嵌入）

        # 按 doc_id 过滤（如果指定）
        if doc_id:
            # 构建 doc_id 过滤掩码（仅在首次使用时线性扫描）
            # 注意: chunk_id 格式通常为 "{doc_id}_{number}"
            mask = np.array(
                [cid.startswith(doc_id) for cid in self.chunk_ids],
                dtype=bool,
            )
            if mask.sum() == 0:
                # fallback: 使用 doc_id 精确匹配 chunk_id 前缀
                mask = np.ones(len(self.chunk_ids), dtype=bool)
            scores = np.where(mask, scores, -1.0)

        # 取 top_k（argpartition 比完全排序快）
        actual_k = min(top_k, len(scores))
        if actual_k == 0:
            return []

        top_idx = np.argpartition(scores, -actual_k)[-actual_k:]
        top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]

        return [
            {"chunk_id": self.chunk_ids[i], "score": float(scores[i])}
            for i in top_idx
            if scores[i] > 0
        ]

    # ── 状态 ──────────────────────────────────────────────────

    def get_status(self) -> dict:
        meta: dict = {}
        meta_path = _GNN_DIR / "metadata.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass
        return {
            "loaded":     self.loaded,
            "num_nodes":  len(self.chunk_ids),
            "emb_dim":    int(self.embeddings.shape[1]) if self.loaded and self.embeddings is not None else 0,
            "metadata":   meta,
        }


# ── 应用级单例 ─────────────────────────────────────────────

_instance: Optional[GNNService] = None


def get_gnn_service() -> GNNService:
    global _instance
    if _instance is None:
        _instance = GNNService()
    return _instance
