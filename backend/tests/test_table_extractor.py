from src.services import table_extractor


def test_table_extractor_available_with_camelot(monkeypatch):
    monkeypatch.setattr(table_extractor, "_CAMELOT_AVAILABLE", True)
    monkeypatch.setattr("src.services.parsing.ocr_engine.is_struct_available", lambda: False)
    assert table_extractor.is_available() is True


def test_table_extractor_available_with_structure(monkeypatch):
    monkeypatch.setattr(table_extractor, "_CAMELOT_AVAILABLE", False)
    monkeypatch.setattr("src.services.parsing.ocr_engine.is_struct_available", lambda: True)
    assert table_extractor.is_available() is True
