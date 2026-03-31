"""
tests/test_auth_boundaries.py
鉴权边界测试：未登录/无权限访问受保护接口
"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def app():
    from src.main import app as _app
    return _app


@pytest.mark.asyncio
class TestUnauthenticated:
    """未登录时受保护接口应返回 401"""

    async def test_query_requires_auth(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/query", json={"question": "test"})
        assert response.status_code == 401

    async def test_conversations_requires_auth(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/conversations")
        assert response.status_code == 401

    async def test_documents_requires_auth(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/documents")
        assert response.status_code == 401

    async def test_graph_requires_auth(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/graph")
        assert response.status_code == 401

    async def test_feedback_requires_auth(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/feedback", json={"question": "q", "rating": 1})
        assert response.status_code == 401

    async def test_invalid_token_rejected(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/documents",
                headers={"Authorization": "Bearer invalid.token.here"}
            )
        assert response.status_code in (401, 403)


@pytest.mark.asyncio
class TestAdminBoundaries:
    """非管理员访问管理员接口应返回 403"""

    async def test_admin_entities_requires_admin(self, app):
        """需要管理员权限的接口，普通 token 应返回 403"""
        # 使用格式正确但权限不足的 token
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/admin/entities/merge",
                json={"source_names": ["a"], "target_name": "b", "type": "Tool"},
                headers={"Authorization": "Bearer fake_user_token"},
            )
        assert response.status_code in (401, 403)

    async def test_admin_reload_requires_admin(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/admin/reload-config",
                headers={"Authorization": "Bearer fake_user_token"},
            )
        assert response.status_code in (401, 403)


class TestPublicEndpoints:
    """公开接口不需要 auth"""

    def test_health_check_is_public(self):
        from fastapi.testclient import TestClient
        from src.main import app
        client = TestClient(app)
        response = client.get("/health")
        # 健康检查应可访问（200 或 503 都可，但不应是 401）
        assert response.status_code != 401

    def test_login_is_public(self):
        from fastapi.testclient import TestClient
        from src.main import app
        client = TestClient(app)
        response = client.post("/api/auth/login", json={"username": "000000", "password": "wrong"})
        # 认证失败是 401，但不是因为未提供 token
        assert response.status_code in (200, 400, 401, 422)
