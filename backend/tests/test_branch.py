"""
tests/test_branch.py
POST /api/conversations/branch 端点单元测试
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from src.routers.conversations import branch_conversation, BranchRequest


def _make_conv(id_: str, user_id: str, messages: list[dict]) -> MagicMock:
    conv = MagicMock()
    conv.id = id_
    conv.user_id = user_id
    conv.title = "测试对话"
    conv.messages = json.dumps(messages)
    conv.branch_from_conversation_id = None
    conv.branch_from_message_index = None
    return conv


def _make_user(uid: str = "user-1") -> MagicMock:
    u = MagicMock()
    u.id = uid
    return u


def _make_db(conv=None) -> AsyncMock:
    db = AsyncMock()
    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = conv
    db.execute.return_value = scalar
    db.add = MagicMock()  # db.add is synchronous in SQLAlchemy AsyncSession
    db.refresh = AsyncMock()
    return db


class TestBranchConversation:
    SOURCE_MSGS = [
        {"role": "user",      "content": "问题一", "id": "m1"},
        {"role": "assistant", "content": "回答一", "id": "m2"},
        {"role": "user",      "content": "问题二", "id": "m3"},
    ]

    @pytest.mark.asyncio
    async def test_normal_branch_creates_new_conv(self):
        source = _make_conv("src-1", "user-1", self.SOURCE_MSGS)
        db = _make_db(source)
        user = _make_user("user-1")

        branched = MagicMock()
        branched.id = "branch-1"
        branched.title = "测试对话 分支"
        branched.branch_from_conversation_id = "src-1"
        branched.branch_from_message_index = 1

        async def fake_refresh(obj):
            obj.id = branched.id
            obj.title = branched.title
            obj.branch_from_conversation_id = branched.branch_from_conversation_id
            obj.branch_from_message_index = branched.branch_from_message_index

        db.refresh.side_effect = fake_refresh

        req = BranchRequest(source_conversation_id="src-1", message_index=1)
        result = await branch_conversation(req, db, user)

        assert result["branch_from_conversation_id"] == "src-1"
        assert result["branch_from_message_index"] == 1
        assert result["message_count"] == 2  # [0, 1] inclusive

    @pytest.mark.asyncio
    async def test_branch_messages_are_prefix_copy(self):
        source = _make_conv("src-1", "user-1", self.SOURCE_MSGS)
        db = _make_db(source)
        user = _make_user("user-1")

        added_conv = None

        def capture_add(obj):
            nonlocal added_conv
            added_conv = obj

        db.add.side_effect = capture_add

        async def fake_refresh(obj):
            pass

        db.refresh.side_effect = fake_refresh

        req = BranchRequest(source_conversation_id="src-1", message_index=1)
        await branch_conversation(req, db, user)

        assert added_conv is not None
        branch_msgs = json.loads(added_conv.messages)
        assert len(branch_msgs) == 2
        assert branch_msgs[0]["content"] == "问题一"
        assert branch_msgs[1]["content"] == "回答一"

    @pytest.mark.asyncio
    async def test_branch_is_independent_deep_copy(self):
        msgs = [{"role": "user", "content": "原始", "id": "m1"}]
        source = _make_conv("src-1", "user-1", msgs)
        db = _make_db(source)
        user = _make_user("user-1")
        db.refresh.side_effect = AsyncMock()

        req = BranchRequest(source_conversation_id="src-1", message_index=0)
        await branch_conversation(req, db, user)

        # 修改原始消息列表不影响已传递给分支的数据
        msgs[0]["content"] = "已修改"
        source.messages = json.dumps(msgs)

        # 分支已经通过 json.dumps 序列化，所以原始 Python 对象改变不影响分支
        # （验证 add 时存的是独立的 JSON 字符串）
        call_args = db.add.call_args[0][0]
        branch_msgs = json.loads(call_args.messages)
        assert branch_msgs[0]["content"] == "原始"

    @pytest.mark.asyncio
    async def test_nonexistent_source_raises_404(self):
        db = _make_db(conv=None)
        user = _make_user("user-1")

        req = BranchRequest(source_conversation_id="no-such-id", message_index=0)
        with pytest.raises(HTTPException) as exc_info:
            await branch_conversation(req, db, user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_message_index_out_of_bounds_raises_400(self):
        source = _make_conv("src-1", "user-1", self.SOURCE_MSGS)
        db = _make_db(source)
        user = _make_user("user-1")

        req = BranchRequest(source_conversation_id="src-1", message_index=9999)
        with pytest.raises(HTTPException) as exc_info:
            await branch_conversation(req, db, user)
        assert exc_info.value.status_code == 400

    def test_negative_message_index_rejected_by_pydantic(self):
        with pytest.raises(Exception):
            BranchRequest(source_conversation_id="src-1", message_index=-1)
