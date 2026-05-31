import pytest

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
    EMBEDDING_DEVICE = "auto"
    REMOTE_EMBEDDING_BATCH_SIZE = 25


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


# ── F126: _resolve_device ────────────────────────────────────────────────────

def test_resolve_device_auto_prefers_cuda(monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert svc._resolve_device("auto") == "cuda"


def test_resolve_device_auto_falls_to_mps_when_no_cuda(monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    mps = getattr(torch.backends, "mps", None)
    if mps is None:
        pytest.skip("torch.backends.mps not available on this platform")
    monkeypatch.setattr(mps, "is_available", lambda: True)
    assert svc._resolve_device("auto") == "mps"


def test_resolve_device_auto_falls_to_cpu_when_no_gpu(monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    mps = getattr(torch.backends, "mps", None)
    if mps is not None:
        monkeypatch.setattr(mps, "is_available", lambda: False)
    assert svc._resolve_device("auto") == "cpu"


def test_resolve_device_explicit_passthrough():
    assert svc._resolve_device("cpu") == "cpu"
    assert svc._resolve_device("cuda") == "cuda"
    assert svc._resolve_device("mps") == "mps"


# ── F125: batch_size configurable ────────────────────────────────────────────

def test_openai_compat_provider_uses_configured_batch_size():
    provider = svc._OpenAICompatEmbeddingProvider(
        api_url="http://example.com", api_key="key", model="test", batch_size=10
    )
    assert provider._batch_size == 10


def test_openai_compat_provider_default_batch_size():
    provider = svc._OpenAICompatEmbeddingProvider(
        api_url="http://example.com", api_key="key", model="test"
    )
    assert provider._batch_size == 25
