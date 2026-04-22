from src.services.image_vector_service import (
    build_image_milvus_text,
    normalize_image_text_values,
)


def test_normalize_image_text_values_accepts_mixed_types():
    values = ["PN-1", 42, {"name": "A"}, None, True]

    normalized = normalize_image_text_values(values)

    assert normalized[0] == "PN-1"
    assert normalized[1] == "42"
    assert '"name": "A"' in normalized[2]
    assert normalized[3] == "True"


def test_build_image_milvus_text_handles_non_string_relations():
    text = build_image_milvus_text(
        summary="装配图摘要",
        part_numbers=["PN-1", {"code": "PN-2"}],
        assembly_relations=[{"from": "A", "to": "B"}, 7],
    )

    assert "装配图摘要" in text
    assert "PN-1" in text
    assert '"code": "PN-2"' in text
    assert '"from": "A"' in text
    assert "7" in text


def test_normalize_image_text_values_decodes_json_string_lists():
    normalized = normalize_image_text_values('["PN-1", {"code": "PN-2"}]')

    assert normalized[0] == "PN-1"
    assert '"code": "PN-2"' in normalized[1]
