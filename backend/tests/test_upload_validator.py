"""Unit tests for upload file validator."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.services.security.upload_validator import (
    validate_upload,
    PDF_ONLY,
    DOCUMENT_TYPES,
    MAGIC_BYTES_MAP,
)

PDF_MAGIC = b"%PDF-1.4 rest of content"
DOCX_MAGIC = b"PK\x03\x04rest of docx"
PNG_MAGIC = b"\x89PNG\r\n\x1a\nrest of png"


def _mock_file(content_type: str, content: bytes, filename: str = "test.pdf") -> MagicMock:
    f = MagicMock()
    f.content_type = content_type
    f.filename = filename
    f.read = AsyncMock(return_value=content)
    return f


def _run(coro):
    return asyncio.run(coro)


class TestValidPdf:
    def test_valid_pdf_returns_content(self):
        f = _mock_file("application/pdf", PDF_MAGIC)
        result = _run(validate_upload(f, PDF_ONLY, max_bytes=10 * 1024 * 1024))
        assert result == PDF_MAGIC

    def test_valid_pdf_no_explicit_allowed_types_defaults_to_pdf_only(self):
        f = _mock_file("application/pdf", PDF_MAGIC)
        result = _run(validate_upload(f))
        assert result == PDF_MAGIC


class TestMimeTypeRejection:
    def test_rejects_wrong_mime_type(self):
        f = _mock_file("image/jpeg", b"\xff\xd8\xff" + b"x" * 100)
        with pytest.raises(HTTPException) as exc:
            _run(validate_upload(f, PDF_ONLY))
        assert exc.value.status_code == 400
        assert "不支持" in exc.value.detail

    def test_accepts_docx_when_allowed(self):
        f = _mock_file(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            DOCX_MAGIC + b"x" * 100,
            filename="doc.docx",
        )
        result = _run(validate_upload(f, DOCUMENT_TYPES))
        assert result.startswith(b"PK\x03\x04")


class TestSizeValidation:
    def test_rejects_empty_file(self):
        f = _mock_file("application/pdf", b"")
        with pytest.raises(HTTPException) as exc:
            _run(validate_upload(f, PDF_ONLY))
        assert exc.value.status_code == 400
        assert "空" in exc.value.detail

    def test_rejects_file_exceeding_max_bytes(self):
        f = _mock_file("application/pdf", PDF_MAGIC + b"x" * 1000)
        with pytest.raises(HTTPException) as exc:
            _run(validate_upload(f, PDF_ONLY, max_bytes=10))
        assert exc.value.status_code == 400
        assert "过大" in exc.value.detail

    def test_accepts_file_exactly_at_limit(self):
        content = PDF_MAGIC
        f = _mock_file("application/pdf", content)
        result = _run(validate_upload(f, PDF_ONLY, max_bytes=len(content)))
        assert result == content


class TestMagicNumber:
    def test_rejects_pdf_with_wrong_magic(self):
        f = _mock_file("application/pdf", b"NOTPDF" + b"x" * 100)
        with pytest.raises(HTTPException) as exc:
            _run(validate_upload(f, PDF_ONLY))
        assert exc.value.status_code == 400
        assert "magic" in exc.value.detail

    def test_accepts_png_with_correct_magic(self):
        f = _mock_file("image/png", PNG_MAGIC + b"x" * 100, filename="img.png")
        from src.services.security.upload_validator import IMAGE_TYPES
        result = _run(validate_upload(f, IMAGE_TYPES))
        assert result.startswith(b"\x89PNG")

    def test_rejects_png_with_jpeg_magic(self):
        f = _mock_file("image/png", b"\xff\xd8\xff" + b"x" * 100, filename="fake.png")
        from src.services.security.upload_validator import IMAGE_TYPES
        with pytest.raises(HTTPException) as exc:
            _run(validate_upload(f, IMAGE_TYPES))
        assert exc.value.status_code == 400
