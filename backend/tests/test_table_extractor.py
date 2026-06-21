from src.services.tables import table_extractor


def test_table_extractor_available_with_camelot(monkeypatch):
    monkeypatch.setattr("src.services.tables.strategies.CAM_ELOT_AVAILABLE", True)
    monkeypatch.setattr("src.services.parsing.ocr_engine.is_struct_available", lambda: False)
    assert table_extractor.is_available() is True


def test_table_extractor_available_with_structure(monkeypatch):
    monkeypatch.setattr("src.services.tables.strategies.CAM_ELOT_AVAILABLE", False)
    monkeypatch.setattr("src.services.parsing.ocr_engine.is_struct_available", lambda: True)
    assert table_extractor.is_available() is True
