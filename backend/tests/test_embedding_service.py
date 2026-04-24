from src.services.retrieval import embedding_service as svc


class _FallbackProvider:
    model_name = "fallback"
    dim = 1024

    def embed_batch(self, texts):
        return [[0.1, 0.2] for _ in texts]


class _FakeSettings:
    DASHSCOPE_API_KEY = "test-key"
    EMBEDDING_QWEN_MODEL = "text-embedding-v3"
    EMBEDDING_QWEN_DIM = 1024
    EMBEDDING_API_URL = ""
    EMBEDDING_API_KEY = ""
    EMBEDDING_MODEL = "models/bge-m3"


def test_embedding_service_falls_back_to_api_when_local_dependency_missing(monkeypatch):
    service = svc.EmbeddingService.__new__(svc.EmbeddingService)
    service._settings = _FakeSettings()
    service._provider = svc._LocalBGEProvider("models/bge-m3")
    monkeypatch.setattr(
        service._provider,
        "embed_batch",
        lambda texts: (_ for _ in ()).throw(ModuleNotFoundError("No module named 'sentence_transformers'")),
    )

    monkeypatch.setattr(
        svc.EmbeddingService,
        "_build_api_fallback_provider",
        staticmethod(lambda settings: _FallbackProvider()),
    )

    result = svc.EmbeddingService.embed_batch(service, ["hello", "world"])

    assert result == [[0.1, 0.2], [0.1, 0.2]]
    assert isinstance(service._provider, _FallbackProvider)
