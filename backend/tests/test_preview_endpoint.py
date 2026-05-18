"""
tests/test_preview_endpoint.py
F120: /api/preview 解析异常应优雅降级为 422
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    driver = MagicMock()
    with patch("src.startup.init_db"), \
         patch("src.startup.init_tables"), \
         patch("src.startup.connect_milvus"), \
         patch("src.startup.get_or_create_collection"), \
         patch("src.core.database.get_driver", return_value=driver), \
         patch("src.core.database._driver", driver):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


@patch("src.routers.docs.ingest.validate_upload")
@patch("src.routers.docs.ingest.parse")
def test_preview_returns_422_when_parse_fails(mock_parse, mock_validate_upload, client):
    mock_validate_upload.return_value = b"%PDF-1.4\n"
    mock_parse.side_effect = ValueError("bad pdf")

    res = client.post(
        "/api/preview",
        files={"file": ("bad.pdf", b"%PDF-1.4\n", "application/pdf")},
    )

    assert res.status_code == 422
    assert res.json()["detail"] == "无法解析 PDF：ValueError"
