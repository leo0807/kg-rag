"""
tests/test_neo4j_writer.py
neo4j_writer 的单元测试
"""
from unittest.mock import MagicMock, patch
from src.models.schemas import DocumentSchema, SectionSchema
from src.services.graph.neo4j_writer import write_document, write_document_incremental


def make_doc(**kwargs) -> DocumentSchema:
    defaults = {
        "doc_id":         "CPS9999",
        "version":        "A",
        "title":          "测试规范",
        "issue_date":     "2024-01-01",
        "total_sections": 2,
        "sections": [
            SectionSchema(chunk_id="CPS9999_1", number="1", title="范围",    content="本规范适用于测试"),
            SectionSchema(chunk_id="CPS9999_2", number="2", title="引用文件", content="无"),
        ],
        "refs": [],
    }
    defaults.update(kwargs)
    return DocumentSchema(**defaults)


def make_mock_driver():
    mock_session = MagicMock()
    mock_driver  = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__  = MagicMock(return_value=False)
    return mock_driver, mock_session


def run_write(doc, mock_driver):
    with patch("src.services.graph.neo4j_writer.get_driver", return_value=mock_driver), \
         patch("src.services.graph.neo4j_writer.embed_texts",
               return_value=[[0.1] * 1024] * len(doc.sections)), \
         patch("src.services.graph.neo4j_writer.upsert_sections"):
        write_document(doc)


class TestWriteDocument:

    def test_runs_document_merge(self):
        driver, session = make_mock_driver()
        run_write(make_doc(), driver)
        assert session.run.called

    def test_passes_correct_doc_id(self):
        driver, session = make_mock_driver()
        run_write(make_doc(doc_id="CPS1234"), driver)
        calls = [
            c for c in session.run.call_args_list
            if "doc_id" in (c.kwargs or {}) and c.kwargs.get("doc_id") == "CPS1234"
        ]
        assert len(calls) > 0

    def test_writes_refs_when_present(self):
        driver, session = make_mock_driver()
        run_write(make_doc(refs=["CPS1214", "CDS0030"]), driver)
        calls = [c for c in session.run.call_args_list if "refs" in (c.kwargs or {})]
        assert len(calls) > 0

    def test_skips_refs_when_empty(self):
        driver, session = make_mock_driver()
        run_write(make_doc(refs=[]), driver)
        calls = [c for c in session.run.call_args_list if "refs" in (c.kwargs or {})]
        assert len(calls) == 0

    def test_explicit_driver_bypasses_get_driver(self):
        """driver kwarg が渡された時 get_driver() を呼ばない"""
        driver, _ = make_mock_driver()
        with patch("src.services.graph.neo4j_writer.get_driver") as mock_get, \
             patch("src.services.graph.neo4j_writer.embed_texts",
                   return_value=[[0.1] * 1024] * 2), \
             patch("src.services.graph.neo4j_writer.upsert_sections"):
            write_document(make_doc(), driver=driver)
        mock_get.assert_not_called()

    def test_no_driver_arg_uses_get_driver(self):
        """driver kwarg を省略した時 get_driver() にフォールバックする"""
        driver, _ = make_mock_driver()
        with patch("src.services.graph.neo4j_writer.get_driver",
                   return_value=driver) as mock_get, \
             patch("src.services.graph.neo4j_writer.embed_texts",
                   return_value=[[0.1] * 1024] * 2), \
             patch("src.services.graph.neo4j_writer.upsert_sections"):
            write_document(make_doc())
        mock_get.assert_called_once()
