"""Unit tests for conversation export (JSON / Markdown / DOCX fallback)."""
import json
from src.services.conversation.exporter import export_json, export_markdown, export_docx

MESSAGES = [
    {"role": "user",      "content": "密封剂施工期是多少？", "timestamp": 1700000000000},
    {"role": "assistant", "content": "施工期为 30 分钟。",   "timestamp": 1700000060000,
     "sources": [{"doc_id": "CPS1220"}, {"doc_id": "CPS1000"}]},
]
META = {"strategy": "parallel", "top_k": 5}
TITLE = "密封工艺问答"


class TestExportJson:
    def test_returns_bytes(self):
        result = export_json(TITLE, MESSAGES, META)
        assert isinstance(result, bytes)

    def test_valid_json(self):
        data = json.loads(export_json(TITLE, MESSAGES, META))
        assert data["title"] == TITLE

    def test_contains_messages(self):
        data = json.loads(export_json(TITLE, MESSAGES, META))
        assert len(data["messages"]) == 2

    def test_contains_meta(self):
        data = json.loads(export_json(TITLE, MESSAGES, META))
        assert data["meta"]["strategy"] == "parallel"

    def test_exported_at_present(self):
        data = json.loads(export_json(TITLE, MESSAGES, META))
        assert "exported_at" in data

    def test_empty_messages(self):
        data = json.loads(export_json(TITLE, [], {}))
        assert data["messages"] == []


class TestExportMarkdown:
    def test_returns_bytes(self):
        result = export_markdown(TITLE, MESSAGES, META)
        assert isinstance(result, bytes)

    def test_title_in_output(self):
        md = export_markdown(TITLE, MESSAGES, META).decode()
        assert TITLE in md

    def test_user_role_translated(self):
        md = export_markdown(TITLE, MESSAGES, META).decode()
        assert "用户" in md

    def test_assistant_role_translated(self):
        md = export_markdown(TITLE, MESSAGES, META).decode()
        assert "AI 助手" in md

    def test_message_content_present(self):
        md = export_markdown(TITLE, MESSAGES, META).decode()
        assert "密封剂施工期" in md
        assert "施工期为 30 分钟" in md

    def test_sources_listed(self):
        md = export_markdown(TITLE, MESSAGES, META).decode()
        assert "CPS1220" in md

    def test_strategy_in_meta_block(self):
        md = export_markdown(TITLE, MESSAGES, META).decode()
        assert "parallel" in md

    def test_empty_messages(self):
        md = export_markdown(TITLE, [], {}).decode()
        assert TITLE in md

    def test_timestamp_rendered(self):
        md = export_markdown(TITLE, MESSAGES, META).decode()
        assert "2023" in md  # unix ts 1700000000 = 2023-11-14


class TestExportDocx:
    def test_returns_bytes(self):
        result = export_docx(TITLE, MESSAGES, META)
        assert isinstance(result, bytes)

    def test_nonempty(self):
        result = export_docx(TITLE, MESSAGES, META)
        assert len(result) > 0

    def test_fallback_when_docx_unavailable(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def _block_docx(name, *args, **kwargs):
            if name == "docx":
                raise ImportError("no docx")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_docx)
        result = export_docx(TITLE, MESSAGES, META)
        # should fall back to markdown bytes
        assert isinstance(result, bytes)
        assert TITLE.encode() in result
