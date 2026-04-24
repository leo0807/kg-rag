import asyncio

from src.routers.graph_api.graph import (
    _append_missing_owner_docs,
    _filter_zero_degree_document_nodes,
    get_graph,
)


def test_append_missing_owner_docs_adds_missing_document_nodes():
    nodes = [
        {"id": "img_1", "type": "Image", "doc_id": "CPS1000", "name": "图片1"},
        {"id": "sec_1", "type": "Section", "doc_id": "CPS1000", "name": "范围"},
    ]

    result = _append_missing_owner_docs(nodes)

    assert any(
        node["type"] == "Document" and node["id"] == "CPS1000"
        for node in result
    )


def test_append_missing_owner_docs_does_not_duplicate_existing_documents():
    nodes = [
        {"id": "CPS1000", "type": "Document", "doc_id": "CPS1000", "name": "CPS1000"},
        {"id": "img_1", "type": "Image", "doc_id": "CPS1000", "name": "图片1"},
    ]

    result = _append_missing_owner_docs(nodes)

    assert sum(1 for node in result if node["type"] == "Document" and node["id"] == "CPS1000") == 1


def test_filter_zero_degree_document_nodes_drops_unconnected_documents():
    nodes = [
        {"id": "CPS0100", "type": "Document", "doc_id": "CPS0100", "name": "CPS0100"},
        {"id": "CPS0200", "type": "Document", "doc_id": "CPS0200", "name": "CPS0200"},
        {"id": "CPS0100_1", "type": "Section", "doc_id": "CPS0100", "name": "范围"},
    ]
    edges = [{"source": "CPS0100", "target": "CPS0100_1", "type": "HAS_SECTION"}]

    result = _filter_zero_degree_document_nodes(nodes, edges)

    assert any(node["id"] == "CPS0100" for node in result)
    assert not any(node["id"] == "CPS0200" for node in result)


class _FakeSession:
    def run(self, cypher, **params):
        if "MATCH (d:Document)" in cypher and "RETURN d.name AS id" in cypher:
            return [{
                "id": "CPS1000",
                "name": "CPS1000",
                "doc_id": "CPS1000",
                "version": "A",
                "type": "Document",
            }]
        if "MATCH (s:Section)" in cypher and "RETURN s.chunk_id AS id" in cypher:
            return [{
                "id": "CPS1000_6_4",
                "name": "工程图纸",
                "doc_id": "CPS1000",
                "level": 2,
                "number": "6.4",
                "has_children": False,
                "type": "Section",
            }]
        if "MATCH (i:Image)" in cypher and "RETURN i.image_id AS id" in cypher:
            return [{
                "id": "img_1",
                "name": "图纸页",
                "doc_id": "CPS1000",
                "description": "",
                "path": "",
                "minio_path": "minio://img_1",
                "is_drawing": True,
            }]
        if "CALL {" in cypher and "HAS_ANNOTATION" in cypher:
            return [{
                "id": "con_1",
                "name": "dimension: 12mm",
                "type": "Constraint",
                "doc_id": "CPS1000",
                "con_type": "dimension",
                "value": "12",
                "value_max": "",
                "unit": "mm",
                "description": "12mm",
                "standard": "",
            }]
        if "'HAS_SECTION' AS type" in cypher:
            return [{"source": "CPS1000", "target": "CPS1000_6_4", "type": "HAS_SECTION"}]
        if "'HAS_IMAGE' AS type" in cypher and "MATCH (d:Document)-[:HAS_IMAGE]->(i:Image)" in cypher:
            return [{"source": "CPS1000", "target": "img_1", "type": "HAS_IMAGE"}]
        if "'HAS_ANNOTATION' AS type" in cypher:
            return [{"source": "img_1", "target": "con_1", "type": "HAS_ANNOTATION"}]
        return []


class _FakeDriver:
    def session(self):
        class _Ctx:
            def __enter__(self_inner):
                return _FakeSession()

            def __exit__(self_inner, exc_type, exc, tb):
                return False

        return _Ctx()


def test_get_graph_emits_has_annotation_edges_for_image_constraints():
    result = asyncio.run(get_graph(doc_id="CPS1000", driver=_FakeDriver()))

    assert any(
        edge["type"] == "HAS_ANNOTATION"
        and edge["source"] == "img_1"
        and edge["target"] == "con_1"
        for edge in result["edges"]
    )
