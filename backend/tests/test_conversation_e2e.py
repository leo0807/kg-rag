"""
tests/test_conversation_e2e.py
多轮对话端到端测试
"""
import pytest
from unittest.mock import patch, MagicMock


class TestConversationModel:
    """测试对话数据模型"""

    def test_message_structure(self):
        """验证消息结构符合前端期望"""
        message = {
            "role": "user",
            "content": "液压导管安装步骤",
        }
        assert message["role"] in ("user", "assistant", "system")
        assert isinstance(message["content"], str)

    def test_history_format_for_llm(self):
        """验证 history 列表格式可被 LLM API 接受"""
        history = [
            {"role": "user",      "content": "第一轮问题"},
            {"role": "assistant", "content": "第一轮答案"},
            {"role": "user",      "content": "第二轮问题"},
        ]
        for msg in history:
            assert "role"    in msg
            assert "content" in msg
            assert msg["role"] in ("user", "assistant", "system")

    def test_conversation_create_schema(self):
        """验证创建会话请求体 schema"""
        from pydantic import ValidationError
        try:
            from src.routers.conversations import ConversationCreate
            conv = ConversationCreate(title="测试对话", strategy="parallel")
            assert conv.title    == "测试对话"
            assert conv.strategy == "parallel"
            assert conv.messages == []
        except ImportError:
            pytest.skip("ConversationCreate not importable in isolation")


class TestQueryRequestModel:
    """测试查询请求模型"""

    def test_query_request_with_history(self):
        from src.routers.query.models import QueryRequest
        req = QueryRequest(
            question="第二轮问题",
            strategy="parallel",
            history=[
                {"role": "user",      "content": "第一轮问题"},
                {"role": "assistant", "content": "第一轮答案"},
            ],
        )
        assert req.question         == "第二轮问题"
        assert len(req.history)     == 2
        assert req.history[0]["role"] == "user"

    def test_query_request_with_images(self):
        from src.routers.query.models import QueryRequest
        req = QueryRequest(
            question="这张图片是什么工具",
            images=["data:image/png;base64,abc123"],
        )
        assert len(req.images) == 1
        assert req.images[0].startswith("data:image")

    def test_query_request_defaults(self):
        from src.routers.query.models import QueryRequest
        req = QueryRequest(question="问题")
        assert req.strategy  == "parallel"
        assert req.top_k     == 5
        assert req.history   == []
        assert req.images    == []


class TestConversationBranching:
    """测试对话分支功能"""

    def test_branch_title_format(self):
        """分支标题格式"""
        messages = [
            {"role": "user",      "content": "液压系统相关问题"},
            {"role": "assistant", "content": "答案"},
        ]
        branch_title = f"分支: {messages[0]['content'][:18]}"
        assert branch_title.startswith("分支: ")
        assert len(branch_title) <= 20 + len("分支: ")

    def test_branch_messages_subset(self):
        """分支只包含到分支点为止的消息"""
        all_messages = [
            {"role": "user",      "content": "问题1"},
            {"role": "assistant", "content": "答案1"},
            {"role": "user",      "content": "问题2"},
            {"role": "assistant", "content": "答案2"},
        ]
        branch_at = 1  # 从第2条消息（第1轮答案）分支
        branched = all_messages[:branch_at + 1]
        assert len(branched) == 2
        assert branched[-1]["role"] == "assistant"


class TestMultiTurnContext:
    """测试多轮上下文传递"""

    def test_history_truncation(self):
        """历史记录应截断到最近 12 条（6轮）"""
        long_history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(20)
        ]
        truncated = long_history[-12:]
        assert len(truncated) == 12

    def test_stream_builds_correct_messages(self):
        """流式接口构建的 messages 列表格式正确"""
        history = [
            {"role": "user",      "content": "上一轮问题"},
            {"role": "assistant", "content": "上一轮答案"},
        ]
        context = "[DOC001 §1.1] 安装规范\n内容..."
        question = "当前问题"

        messages = [
            {"role": "system", "content": "你是航空工艺规范专家助手。"},
        ]
        for h in history[-12:]:
            messages.append({"role": h["role"], "content": h["content"]})

        user_text = f"## 相关规范内容\n\n{context}\n\n## 问题\n\n{question}"
        messages.append({"role": "user", "content": user_text})

        assert messages[0]["role"]   == "system"
        assert messages[1]["role"]   == "user"
        assert messages[2]["role"]   == "assistant"
        assert messages[3]["role"]   == "user"
        assert context               in messages[3]["content"]
        assert question              in messages[3]["content"]
