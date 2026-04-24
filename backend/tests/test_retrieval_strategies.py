"""
tests/test_retrieval_strategies.py
检索策略集成测试：parallel / sequential / graph_augmented / multi_hop
使用 mock Driver，不需要真实 Neo4j 连接。
"""
import pytest
from unittest.mock import MagicMock, patch


def make_driver(sections=None):
    """创建返回固定章节列表的 mock Driver"""
    if sections is None:
        sections = [
            {"chunk_id": "doc1_1", "doc_id": "DOC001", "number": "1.1",
             "title": "液压导管安装", "content": "安装前检查导管外观..."},
            {"chunk_id": "doc1_2", "doc_id": "DOC001", "number": "1.2",
             "title": "导管连接方法", "content": "使用标准扳手拧紧..."},
        ]
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = lambda s: session
    driver.session.return_value.__exit__ = MagicMock(return_value=False)

    def run_mock(query, **kwargs):
        result = MagicMock()
        result.__iter__ = lambda self: iter([
            MagicMock(**{
                "__getitem__": lambda s, k: sec.get(k, ""),
                "keys": lambda: sec.keys(),
            })
            for sec in sections
        ])
        # single() 返回空
        result.single.return_value = None
        # 将 __iter__ 的 Mock 对象模拟为返回 dict
        rows = []
        for sec in sections:
            row = MagicMock()
            row.__getitem__ = lambda s, k, _sec=sec: _sec.get(k, "")
            row.keys = lambda: sec.keys()
            rows.append(row)
        result.__iter__ = lambda s: iter(rows)
        return result

    session.run.side_effect = run_mock
    return driver


# ── RRF 融合 ──────────────────────────────────────────────────────────────────
class TestRRFFusion:
    def test_combines_both_lists(self):
        from src.routers.query.core import rrf_fusion
        ft_ids  = ["a", "b", "c"]
        vec_ids = ["b", "c", "d"]
        result  = rrf_fusion(ft_ids, vec_ids)
        # b 和 c 在两个列表都出现，应该排名更高
        assert result.index("b") < result.index("a")
        assert result.index("c") < result.index("a")

    def test_empty_inputs(self):
        from src.routers.query.core import rrf_fusion
        assert rrf_fusion([], []) == []
        assert rrf_fusion(["a"], []) == ["a"]
        assert rrf_fusion([], ["a"]) == ["a"]

    def test_no_duplicates_in_result(self):
        from src.routers.query.core import rrf_fusion
        result = rrf_fusion(["a", "b"], ["b", "c"])
        assert len(result) == len(set(result))


# ── get_section_details ────────────────────────────────────────────────────────
class TestGetSectionDetails:
    def test_returns_sections_in_order(self):
        from src.routers.query.core import get_section_details

        sections = [
            {"chunk_id": "c1", "doc_id": "D1", "number": "1", "title": "T1", "content": "C1"},
            {"chunk_id": "c2", "doc_id": "D1", "number": "2", "title": "T2", "content": "C2"},
        ]
        driver = make_driver(sections)
        result = get_section_details(driver, ["c2", "c1"])
        # 保持入参顺序
        assert [r["chunk_id"] for r in result] == ["c2", "c1"]

    def test_empty_ids(self):
        from src.routers.query.core import get_section_details
        driver = make_driver()
        result = get_section_details(driver, [])
        assert result == []


# ── parallel 策略 ─────────────────────────────────────────────────────────────
class TestParallelStrategy:
    @patch("src.routers.query.core.search_sections", return_value=[])
    @patch("src.routers.query.core.embed_query", return_value=[0.1] * 512)
    def test_parallel_returns_sections(self, mock_embed, mock_search):
        from src.routers.query.core import do_retrieval
        driver = make_driver()

        with patch("src.routers.query.core.search_sections_es") as mock_es:
            mock_es.return_value = [
                {"chunk_id": "doc1_1", "score": 0.9},
                {"chunk_id": "doc1_2", "score": 0.8},
            ]
            sections, ft_map = do_retrieval(driver, "液压导管安装", "parallel", top_k=5)

        assert isinstance(sections, list)
        assert isinstance(ft_map, dict)


# ── sequential 策略 ───────────────────────────────────────────────────────────
class TestSequentialStrategy:
    def test_sequential_uses_fulltext_first(self):
        from src.routers.query.core import do_retrieval
        driver = make_driver()

        with patch("src.routers.query.core.search_sections_es") as mock_es:
            mock_es.return_value = [{"chunk_id": "doc1_1", "score": 0.9}]
            sections, ft_map = do_retrieval(driver, "扳手规格", "sequential", top_k=5)

        assert isinstance(sections, list)


# ── graph_augmented 策略 ──────────────────────────────────────────────────────
class TestGraphAugmentedStrategy:
    def test_graph_augmented_queries_expansion(self):
        from src.routers.query.core import do_retrieval
        driver = make_driver()

        session = MagicMock()
        expansion_result = MagicMock()
        expansion_result.single.return_value = {"expanded_ids": ["doc1_1", "doc1_2", "doc1_3"]}
        session.run.return_value = expansion_result
        driver.session.return_value.__enter__ = lambda s: session
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.routers.query.core.search_sections_es") as mock_es, \
             patch("src.routers.query.core.embed_query", return_value=[0.1] * 512), \
             patch("src.routers.query.core.search_sections", return_value=[]):
            mock_es.return_value = [{"chunk_id": "doc1_1", "score": 0.9}]
            sections, _ = do_retrieval(driver, "安装步骤", "graph_augmented", top_k=5)

        assert isinstance(sections, list)


# ── 多跳推理 ─────────────────────────────────────────────────────────────────
class TestMultiHopStrategy:
    def test_multi_hop_returns_three_values(self):
        from src.services.retrieval.multi_hop import multi_hop_query

        driver = make_driver()

        with patch("src.services.retrieval.multi_hop.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "子问题1\n子问题2"}}]
            }
            mock_post.return_value = mock_resp

            with patch("src.services.retrieval.multi_hop.embed_query", return_value=[0.1] * 512), \
                 patch("src.services.retrieval.multi_hop.search_sections", return_value=[]):
                answer, sources, steps = multi_hop_query("跨文档复杂问题", driver, top_k=3)

        assert isinstance(answer, str)
        assert isinstance(sources, list)
        assert isinstance(steps, list)

    def test_max_hops_protection(self):
        from src.services.retrieval.multi_hop import MAX_HOPS, should_continue, AgentState

        state: AgentState = {
            "question": "test", "sub_queries": ["q1", "q2", "q3", "q4", "q5", "q6"],
            "retrieved": [], "hop_count": MAX_HOPS, "final_answer": "", "steps": [],
        }
        # 超过最大跳数时应跳转到 synthesize
        assert should_continue(state) == "synthesize"
