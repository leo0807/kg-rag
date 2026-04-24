"""
tests/test_stream_sse.py
流式 SSE 响应测试：验证 /api/query/stream 的事件格式
"""
import asyncio
import json
import sys
import types
from unittest.mock import MagicMock, patch
from starlette.requests import Request


def _optional_dependency_stubs() -> dict[str, object]:
    fake_jose = types.SimpleNamespace(jwt=types.SimpleNamespace(), JWTError=Exception)
    fake_auth_deps = types.SimpleNamespace(get_optional_user=lambda: None)
    fake_observability = types.SimpleNamespace(send_generation=lambda *args, **kwargs: None)
    fake_query_sync = types.SimpleNamespace(query_sync=lambda *args, **kwargs: None)
    fake_query_compare = types.SimpleNamespace(query_compare=lambda *args, **kwargs: None)
    return {
        "jose": fake_jose,
        "src.auth.deps": fake_auth_deps,
        "src.core.observability": fake_observability,
        "src.routers.query.sync": fake_query_sync,
        "src.routers.query.compare": fake_query_compare,
    }


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


class TestStreamEndpoint:
    """集成测试：/api/query/stream 返回正确的 SSE 流"""

    def test_stream_returns_event_stream_content_type(self):
        async def _run():
            with patch.dict(sys.modules, _optional_dependency_stubs()):
                from src.routers.query.stream import query_stream

                async def _receive():
                    return {"type": "http.request", "body": b"", "more_body": False}

                request = Request({
                    "type": "http",
                    "method": "POST",
                    "path": "/api/query/stream",
                    "headers": [],
                }, _receive)

                req = types.SimpleNamespace(
                    question="test",
                    strategy="parallel",
                    top_k=5,
                    history=[],
                    images=[],
                    use_hyde=False,
                    hyde_alpha=0.5,
                )
                response = await query_stream(
                    request=request,
                    req=req,
                    driver=MagicMock(),
                    current_user=None,
                )
                return response

        response = asyncio.run(_run())
        assert response.media_type == "text/event-stream"

    def test_sse_error_event_format(self):
        """错误事件格式"""
        event = {"type": "error", "content": "连接失败"}
        assert event["type"] == "error"
        assert isinstance(event["content"], str)

    def test_stream_wraps_unhandled_generator_errors_as_sse_error(self):
        async def _run():
            with patch.dict(sys.modules, _optional_dependency_stubs()):
                from src.routers.query.stream import query_stream

                async def _receive():
                    return {"type": "http.request", "body": b"", "more_body": False}

                request = Request({
                    "type": "http",
                    "method": "POST",
                    "path": "/api/query/stream",
                    "headers": [],
                }, _receive)

                req = types.SimpleNamespace(
                    question="test",
                    strategy="parallel",
                    top_k=5,
                    history=[],
                    images=[],
                    use_hyde=False,
                    hyde_alpha=0.5,
                )
                with patch("src.routers.query.stream.do_retrieval", side_effect=RuntimeError("boom")), \
                     patch("src.services.retrieval.embedder.embed_texts", return_value=[None]):
                    response = await query_stream(
                        request=request,
                        req=req,
                        driver=MagicMock(),
                        current_user=None,
                    )

                    chunks = []
                    async for chunk in response.body_iterator:
                        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

            return "".join(chunks)

        raw = asyncio.run(_run())
        events = parse_sse_events(raw)

        assert any(e.get("type") == "status" for e in events)
        assert any(e.get("type") == "error" for e in events)
        assert events[-1]["type"] == "__done__"
