from src.routers.graph_api.graph import _append_missing_owner_docs


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
