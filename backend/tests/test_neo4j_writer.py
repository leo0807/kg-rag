"""
tests/test_neo4j_writer.py
neo4j_writer 的单元测试

用 Mock 隔离外部依赖
  neo4j_writer 依赖真实的 Neo4j 连接，但单元测试不应该依赖外部服务。
  Mock 让我们用假对象替换真实的 driver，
  验证代码是否调用了正确的 Cypher 语句。
"""
from unittest.mock import MagicMock, patch, call
from src.models.schemas import DocumentSchema, SectionSchema
from src.services.neo4j_writer import write_document


def make_doc(**kwargs) -> DocumentSchema:
    """构造测试用的文档对象"""
    defaults = {
        "doc_id":         "CPS9999",
        "version":        "A",
        "title":          "测试规范",
        "issue_date":     "2024-01-01",
        "total_sections": 2,
        "sections": [
            SectionSchema(
                chunk_id="CPS9999_1",
                number="1",
                title="范围",
                content="本规范适用于测试",
            ),
            SectionSchema(
                chunk_id="CPS9999_2",
                number="2",
                title="引用文件",
                content="无",
            ),
        ],
        "refs": [],
    }
    defaults.update(kwargs)
    return DocumentSchema(**defaults)


class TestWriteDocument:

    def test_runs_document_merge(self):
        """write_document 应该执行 MERGE Document 节点的 Cypher"""
        mock_session  = MagicMock()
        mock_driver   = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__  = MagicMock(return_value=False)

        with patch("src.services.neo4j_writer.get_driver", return_value=mock_driver):
            write_document(make_doc())

        # 验证 session.run 被调用了
        assert mock_session.run.called

    def test_passes_correct_doc_id(self):
        """写入时应该传入正确的 doc_id 参数"""
        mock_session = MagicMock()
        mock_driver  = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__  = MagicMock(return_value=False)

        with patch("src.services.neo4j_writer.get_driver", return_value=mock_driver):
            write_document(make_doc(doc_id="CPS1234"))

        # 找到包含 doc_id 参数的调用
        calls_with_doc_id = [
            c for c in mock_session.run.call_args_list
            if "doc_id" in (c.kwargs or {}) and c.kwargs.get("doc_id") == "CPS1234"
        ]
        assert len(calls_with_doc_id) > 0, "没有找到传入 doc_id=CPS1234 的调用"

    def test_writes_refs_when_present(self):
        """有引用文件时应该执行引用关系的写入"""
        mock_session = MagicMock()
        mock_driver  = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__  = MagicMock(return_value=False)

        with patch("src.services.neo4j_writer.get_driver", return_value=mock_driver):
            write_document(make_doc(refs=["CPS1214", "CDS0030"]))

        # 找到包含 refs 参数的调用
        calls_with_refs = [
            c for c in mock_session.run.call_args_list
            if "refs" in (c.kwargs or {})
        ]
        assert len(calls_with_refs) > 0, "有引用文件时应该执行引用关系写入"

    def test_skips_refs_when_empty(self):
        """没有引用文件时不应该执行引用关系写入"""
        mock_session = MagicMock()
        mock_driver  = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__  = MagicMock(return_value=False)

        with patch("src.services.neo4j_writer.get_driver", return_value=mock_driver):
            write_document(make_doc(refs=[]))

        calls_with_refs = [
            c for c in mock_session.run.call_args_list
            if "refs" in (c.kwargs or {})
        ]
        assert len(calls_with_refs) == 0, "没有引用文件时不应该执行引用关系写入"