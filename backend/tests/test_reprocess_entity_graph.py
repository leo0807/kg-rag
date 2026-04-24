import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.services.graph.entity_writer import _collect_section_entities
from src.services.ingestion.reprocess_service import _run_entities, _run_tables


def test_collect_section_entities_anchors_relation_endpoints():
    tools, materials, processes, relations = _collect_section_entities({
        "tools": [],
        "materials": ["密封胶A"],
        "processes": [],
        "relations": [
            {
                "from_type": "Process",
                "from_name": "涂胶",
                "rel": "REQUIRES_TOOL",
                "to_type": "Tool",
                "to_name": "机器人自动涂胶设备",
            },
            {
                "from_type": "Material",
                "from_name": "密封胶B",
                "rel": "ALTERNATIVE_TO",
                "to_type": "Material",
                "to_name": "密封胶A",
            },
        ],
    })

    assert tools == ["机器人自动涂胶设备"]
    assert materials == ["密封胶A", "密封胶B"]
    assert processes == ["涂胶"]
    assert len(relations) == 2


def test_run_entities_resets_document_entity_graph_before_write():
    driver = MagicMock()
    sections = [{"chunk_id": "CPS0100_1", "title": "范围", "content": "测试内容"}]
    task = {}
    entity_data = [{"chunk_id": "CPS0100_1", "tools": ["设备"], "materials": [], "processes": [], "relations": []}]

    fake_entity_extractor = SimpleNamespace(extract_entities_from_sections=MagicMock(return_value=entity_data))
    with patch.dict(sys.modules, {"src.services.graph.entity_extractor": fake_entity_extractor}), \
         patch("src.services.graph.entity_writer.reset_document_entity_graph") as reset_graph, \
         patch("src.services.graph.entity_writer.write_entities") as write_entities:
        result = _run_entities(driver, "CPS0100", sections, task, lambda *_: None)

    assert result == 1
    reset_graph.assert_called_once_with(driver, "CPS0100")
    write_entities.assert_called_once_with(driver, "CPS0100", entity_data)


def test_run_tables_resets_and_writes_tables():
    driver = MagicMock()
    sections = [{"chunk_id": "CPS0100_4_1", "number": "4.1", "page_idx": 3}]
    task = {}
    table_data = [{
        "table_id": "CPS0100_tbl_0",
        "chunk_id": "CPS0100_4_1",
        "markdown": "| 参数 | 值 |",
        "rows_json": "[]",
        "page_index": 3,
        "constraints": [],
    }]

    with patch("src.services.tables.table_extractor.is_available", return_value=True), \
         patch("src.services.tables.table_extractor.extract_tables_full", return_value=table_data), \
         patch("src.services.graph.entity_writer.reset_document_tables") as reset_tables, \
         patch("src.services.graph.entity_writer.write_tables") as write_tables:
        result = _run_tables(driver, "CPS0100", "/tmp/CPS0100.pdf", sections, task, lambda *_: None)

    assert result == 1
    reset_tables.assert_called_once_with(driver, "CPS0100")
    write_tables.assert_called_once_with(driver, "CPS0100", table_data)
