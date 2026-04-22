from pathlib import Path
from unittest.mock import MagicMock

from src.services.ingestion.reprocess_service import _prepare_reprocess_pdf


def test_prepare_reprocess_pdf_converts_docx(monkeypatch, tmp_path):
    source = tmp_path / "CPS1000.docx"
    source.write_text("dummy", encoding="utf-8")
    converted = tmp_path / "CPS1000.pdf"
    converted.write_text("pdf", encoding="utf-8")

    monkeypatch.setattr(
        "src.services.parsing.parser._convert_office_to_pdf",
        lambda path: converted,
    )

    pdf_path, cleanup_paths = _prepare_reprocess_pdf("CPS1000", source, MagicMock())

    assert pdf_path == converted
    assert cleanup_paths == [converted]


def test_prepare_reprocess_pdf_keeps_native_pdf(tmp_path):
    pdf = tmp_path / "CPS1000.pdf"
    pdf.write_text("pdf", encoding="utf-8")

    pdf_path, cleanup_paths = _prepare_reprocess_pdf("CPS1000", pdf, MagicMock())

    assert pdf_path == pdf
    assert cleanup_paths == []
