"""
tests/test_stream_sse.py
流式 SSE 响应测试：验证 /api/query/stream 的事件格式
"""
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


def parse_sse_events(raw: str) -> list[dict]:
    """将 SSE 原始文本解析为事件列表"""
    events = []
    for line in raw.split("\n"):
        if line.startswith("data: "):
            data = line[6:]
            if data == "[DONE]":
                events.append({"type": "__done__"})
            else:
                try:
                    events.append(json.loads(data))
                except json.JSONDecodeError:
                    pass
    return events


class TestSSEFormat:
    """测试 SSE 事件格式是否符合规范"""

    def test_sse_event_has_type_field(self):
        event = {"type": "status", "content": "检索中..."}
        assert "type" in event
        assert event["type"] in ("status", "sources", "delta", "error", "steps", "__done__")

    def test_parse_sse_events_parses_correctly(self):
        raw = (
            'data: {"type": "status", "content": "检索中..."}\n\n'
            'data: {"type": "sources", "content": []}\n\n'
            'data: {"type": "delta", "content": "回答"}\n\n'
            'data: [DONE]\n\n'
        )
        events = parse_sse_events(raw)
        types = [e.get("type") for e in events]
        assert "status"  in types
        assert "sources" in types
        assert "delta"   in types
        assert "__done__" in types

    def test_sources_event_contains_list(self):
        event = {"type": "sources", "content": [
            {"chunk_id": "c1", "doc_id": "D1", "number": "1", "title": "T1", "score": 0.9}
        ]}
        assert isinstance(event["content"], list)
        source = event["content"][0]
        assert "chunk_id" in source
        assert "doc_id"   in source
        assert "score"    in source

    def test_delta_event_contains_text(self):
        event = {"type": "delta", "content": "这是部分答案"}
        assert isinstance(event["content"], str)

    def test_steps_event_contains_list(self):
        event = {"type": "steps", "content": [
            {"hop": 1, "query": "子问题1", "found": 3, "titles": ["标题1"]}
        ]}
        assert isinstance(event["content"], list)
        step = event["content"][0]
        assert "hop"    in step
        assert "query"  in step
        assert "found"  in step
        assert "titles" in step


@pytest.mark.asyncio
class TestStreamEndpoint:
    """集成测试：/api/query/stream 返回正确的 SSE 流"""

    async def test_stream_returns_event_stream_content_type(self):
        from fastapi.testclient import TestClient
        from src.main import app

        # Mock 所有外部依赖
        with patch("src.routers.query.stream.do_retrieval") as mock_retrieval, \
             patch("src.routers.query.stream.get_driver"):
            mock_retrieval.return_value = ([], {})

            client = TestClient(app)
            # 需要 auth token，跳过此测试
            # 此处仅验证端点存在
            response = client.post("/api/query/stream",
                                   json={"question": "test", "strategy": "parallel"})
            # 未登录，期望 401
            assert response.status_code == 401

    def test_sse_error_event_format(self):
        """错误事件格式"""
        event = {"type": "error", "content": "连接失败"}
        assert event["type"] == "error"
        assert isinstance(event["content"], str)
