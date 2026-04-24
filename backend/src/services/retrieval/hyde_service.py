"""
HyDE — Hypothetical Document Embeddings

生成"假设答案"并与原始问题向量融合，提升向量检索召回率。
参考论文: Gao et al. 2022 "Precise Zero-Shot Dense Retrieval without Relevance Labels"
"""
import asyncio
import logging
import numpy as np

from ..ai.llm_service      import get_llm_service
from .embedding_service import get_embedding_service

logger = logging.getLogger(__name__)

_HYDE_PROMPT = """\
你是一位航空制造工艺专家。

请根据以下问题，生成一段可能出现在航空工艺规范文档中的标准技术段落。
要求：
- 使用正式的工艺规范语言风格
- 包含具体的技术参数和操作步骤
- 长度约100-150字
- 直接输出段落内容，不要说明"这是假设"或添加前缀

问题：{question}

规范文档内容："""


class HyDEService:
    def generate_hypothetical_answer(self, question: str) -> str:
        """同步：调用 LLM 生成假设答案段落。"""
        prompt = _HYDE_PROMPT.format(question=question)
        try:
            return get_llm_service().chat(
                [{"role": "user", "content": prompt}],
                max_tokens=300,
            )
        except Exception as e:
            logger.warning("HyDE 假设答案生成失败: %s", e)
            return question  # 降级：直接用原问题

    def get_hyde_embedding(self, question: str) -> tuple[list[float], str]:
        """同步：返回 (假设答案向量, 假设答案文本)。"""
        hypothetical = self.generate_hypothetical_answer(question)
        embedding = get_embedding_service().embed(hypothetical)
        return embedding, hypothetical

    def hybrid_embedding(
        self, question: str, alpha: float = 0.5
    ) -> list[float]:
        """
        融合原始问题向量和假设答案向量。
        alpha 为假设答案权重，1-alpha 为原始问题权重。
        融合后 L2 归一化，与 Milvus IP 内积度量兼容。
        """
        svc = get_embedding_service()
        q_emb = np.array(svc.embed(question), dtype=np.float32)
        h_emb, hypo_text = self.get_hyde_embedding(question)
        h_emb = np.array(h_emb, dtype=np.float32)

        logger.debug("HyDE 假设答案（前80字）: %s", hypo_text[:80])

        fused = alpha * h_emb + (1.0 - alpha) * q_emb
        norm = np.linalg.norm(fused)
        if norm > 0:
            fused = fused / norm
        return fused.tolist()


_instance: HyDEService | None = None


def get_hyde_service() -> HyDEService:
    global _instance
    if _instance is None:
        _instance = HyDEService()
    return _instance
