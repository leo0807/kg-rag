"""
tests/test_routes.py
API 路由集成测试
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def mock_session():
    session = MagicMock()
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    session.run.return_value = mock_result
    return session


@pytest.fixture
def mock_driver(mock_session):
    driver = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    driver.session.return_value.__exit__  = MagicMock(return_value=False)
    return driver, mock_session


@pytest.fixture
def client(mock_driver):
    driver, _ = mock_driver
    with patch("src.main.init_db"), \
         patch("src.main.init_tables"), \
         patch("src.main.connect_milvus"), \
         patch("src.main.get_or_create_collection"), \
         patch("src.core.database.get_driver", return_value=driver), \
         patch("src.core.database._driver", driver):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200

    def test_health_returns_ok_status(self, client):
        res = client.get("/api/health")
        assert res.json()["status"] == "OK"

    def test_health_returns_version(self, client):
        res = client.get("/api/health")
        assert "version" in res.json()


class TestQueryEndpoint:

    def test_empty_question_returns_400(self, client):
        res = client.post("/api/query", json={"question": ""})
        assert res.status_code == 400

    def test_blank_question_returns_400(self, client):
        res = client.post("/api/query", json={"question": "   "})
        assert res.status_code == 400

    def test_valid_question_returns_200(self, client):
        res = client.post("/api/query", json={"question": "液压导管修理"})
        assert res.status_code == 200

    def test_response_has_required_fields(self, client):
        res = client.post("/api/query", json={"question": "液压导管修理"})
        data = res.json()
        assert "answer"  in data
        assert "sources" in data


class TestDocumentsEndpoint:

    def test_documents_returns_200(self, client):
        res = client.get("/api/documents")
        assert res.status_code == 200

    def test_documents_returns_list(self, client):
        res = client.get("/api/documents")
        data = res.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_documents_returns_pagination_fields(self, client):
        res = client.get("/api/documents")
        data = res.json()
        assert "total"    in data
        assert "page"     in data
        assert "per_page" in data
        assert "pages"    in data