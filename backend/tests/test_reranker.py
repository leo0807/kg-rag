"""
tests/test_reranker.py
Reranker 效果回归测试：验证精排结果质量
"""
import pytest
from unittest.mock import MagicMock, patch


# ── 单元测试：rerank 函数行为 ──────────────────────────────────────────────────

class TestRerankOrder:
    """验证 rerank 按分数降序返回"""

    @patch("src.services.retrieval.reranker._get_reranker")
    def test_reranker_sorts_by_score_descending(self, mock_get):
        """分数高的结果应排在前面"""
        from src.services.retrieval.reranker import rerank

        mock_model = MagicMock()
        # predict 返回顺序：第1条低分，第2条高分，第3条中分
        mock_model.predict.return_value = [0.2, 0.9, 0.5]
        mock_get.return_value = mock_model

        sections = [
            {"chunk_id": "c1", "content": "安装螺栓时使用力矩扳手"},
            {"chunk_id": "c2", "content": "液压管路安装前检查外观"},
            {"chunk_id": "c3", "content": "连接器插接后检查锁定"},
        ]
        result = rerank("液压管路安装检查", sections, top_k=3)

        # c2 得分最高(0.9)应排第一，c3(0.5)第二，c1(0.2)第三
        assert result[0]["chunk_id"] == "c2"
        assert result[1]["chunk_id"] == "c3"
        assert result[2]["chunk_id"] == "c1"

    @patch("src.services.retrieval.reranker._get_reranker")
    def test_reranker_respects_top_k(self, mock_get):
        """top_k 参数限制返回数量"""
        from src.services.retrieval.reranker import rerank

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.8, 0.7, 0.6, 0.5]
        mock_get.return_value = mock_model

        sections = [{"chunk_id": f"c{i}", "content": f"内容{i}"} for i in range(5)]
        result = rerank("查询词", sections, top_k=3)
        assert len(result) == 3

    @patch("src.services.retrieval.reranker._get_reranker")
    def test_reranker_returns_all_when_top_k_exceeds_input(self, mock_get):
        """top_k 大于输入数量时，返回全部"""
        from src.services.retrieval.reranker import rerank

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.8, 0.6]
        mock_get.return_value = mock_model

        sections = [
            {"chunk_id": "c1", "content": "内容1"},
            {"chunk_id": "c2", "content": "内容2"},
        ]
        result = rerank("查询词", sections, top_k=10)
        assert len(result) == 2

    @patch("src.services.retrieval.reranker._get_reranker")
    def test_reranker_preserves_original_fields(self, mock_get):
        """rerank 返回原始 section 字典（含所有字段）"""
        from src.services.retrieval.reranker import rerank

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.7]
        mock_get.return_value = mock_model

        sections = [{
            "chunk_id": "c1",
            "doc_id": "DOC001",
            "number": "2.3",
            "title": "安装步骤",
            "content": "拧紧螺栓至规定力矩",
        }]
        result = rerank("安装步骤", sections, top_k=1)

        assert result[0]["chunk_id"] == "c1"
        assert result[0]["doc_id"]   == "DOC001"
        assert result[0]["number"]   == "2.3"
        assert result[0]["title"]    == "安装步骤"

    @patch("src.services.retrieval.reranker._get_reranker")
    def test_reranker_handles_empty_sections(self, mock_get):
        """空列表输入时返回空列表"""
        from src.services.retrieval.reranker import rerank

        mock_model = MagicMock()
        mock_get.return_value = mock_model

        result = rerank("查询词", [], top_k=5)
        assert result == []
        mock_model.predict.assert_not_called()


class TestRerankTruncation:
    """验证内容截断不丢失 chunk_id"""

    @patch("src.services.retrieval.reranker._get_reranker")
    def test_long_content_is_truncated_before_predict(self, mock_get):
        """超长内容应被截断，避免模型 OOM"""
        from src.services.retrieval.reranker import rerank

        mock_model = MagicMock()
        mock_model.predict.return_value = [0.5]
        mock_get.return_value = mock_model

        # 4000 字符的内容
        long_section = {"chunk_id": "c1", "content": "A" * 4000}
        rerank("短查询", [long_section], top_k=1)

        call_args = mock_model.predict.call_args
        # predict 收到的 pairs 中，内容长度应 <= 1024
        pairs = call_args[0][0]
        assert len(pairs[0][1]) <= 1024


class TestRerankQuality:
    """回归测试：验证精排在典型航空场景下产出合理排序"""

    def test_relevant_section_ranks_higher_than_irrelevant(self):
        """相关段落得分应高于不相关段落（不需要真实模型，使用 mock 验证逻辑链路）"""
        with patch("src.services.retrieval.reranker._get_reranker") as mock_get:
            from src.services.retrieval.reranker import rerank

            mock_model = MagicMock()
            # 假设真正相关的段落排在第二位（验证 rerank 能够将其提升）
            mock_model.predict.return_value = [0.1, 0.95]
            mock_get.return_value = mock_model

            sections = [
                {"chunk_id": "irrelevant", "content": "工厂卫生管理规定"},
                {"chunk_id": "relevant",   "content": "液压管路安装前应检查外观无损伤"},
            ]
            result = rerank("液压管路安装检查", sections, top_k=2)

            assert result[0]["chunk_id"] == "relevant"
            assert result[1]["chunk_id"] == "irrelevant"
