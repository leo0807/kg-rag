from unittest.mock import MagicMock

from src.services.ai.service import get_llm_service
from src.services.retrieval.embedding_service import get_embedding_service
from src.services.retrieval.reranker import rerank
from src.services.runtime.model_settings import DEFAULT_SETTINGS, use_runtime_settings


def test_default_settings_include_runtime_model_keys():
    assert "llm_provider" in DEFAULT_SETTINGS
    assert "embedding_provider" in DEFAULT_SETTINGS
    assert "reranker_api_url" in DEFAULT_SETTINGS
    assert "vlm_model" in DEFAULT_SETTINGS


def test_llm_service_uses_runtime_override():
    with use_runtime_settings(
        {
            "llm_mode": "api",
            "llm_provider": "",
            "llm_api_url": "https://example.com/v1",
            "llm_api_key": "token-123",
            "llm_model": "custom-chat-model",
        }
    ):
        service = get_llm_service()

    assert service.model_name == "custom-chat-model"
    assert service._provider._url == "https://example.com/v1"
    assert service._provider._key == "token-123"


def test_embedding_service_uses_runtime_override():
    with use_runtime_settings(
        {
            "embedding_mode": "api",
            "embedding_provider": "",
            "embedding_api_url": "https://embed.example.com/v1",
            "embedding_api_key": "embed-token",
            "embedding_model": "custom-embedding-model",
        }
    ):
        service = get_embedding_service()

    assert service.model_name == "custom-embedding-model"
    assert service._provider._url == "https://embed.example.com/v1"
    assert service._provider._key == "embed-token"


def test_reranker_api_mode_uses_custom_endpoint(monkeypatch):
    response = MagicMock()
    response.json.return_value = {
        "results": [
            {"index": 0, "relevance_score": 0.2},
            {"index": 1, "relevance_score": 0.9},
        ]
    }
    response.raise_for_status.return_value = None

    post = MagicMock(return_value=response)
    monkeypatch.setattr("src.services.retrieval.reranker.requests.post", post)

    sections = [
        {"chunk_id": "c1", "content": "普通章节"},
        {"chunk_id": "c2", "content": "最相关章节"},
    ]
    with use_runtime_settings(
        {
            "reranker_mode": "api",
            "reranker_api_url": "https://rerank.example.com",
            "reranker_api_key": "rerank-token",
            "reranker_model": "custom-reranker",
        }
    ):
        result = rerank("查询词", sections, top_k=2)

    assert [item["chunk_id"] for item in result] == ["c2", "c1"]
    post.assert_called_once()
