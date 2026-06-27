#!/usr/bin/env python3
"""
Edge embedding server — offline INT8 ONNX inference for industrial PCs (工控机).

Serves a local HTTP API compatible with the cloud embedding service so that
factory-floor devices can vectorize text without network access.

Usage:
  # 1. Export INT8 model first (run on dev machine with internet):
  #    python scripts/export_onnx_embedder.py --quantize int8 --output-dir models/bge-m3-onnx
  #    scp -r models/bge-m3-onnx operator@workstation:/opt/aviation-embed/model

  # 2. Start server on edge device (no internet required):
  #    pip install onnxruntime fastapi uvicorn  # one-time, from offline wheel cache
  #    python scripts/edge_embedding_server.py --model-dir /opt/aviation-embed/model

  # 3. Client call (same API as cloud service):
  #    curl http://localhost:6006/embed -d '{"texts": ["液压系统安装规范"]}'

Options:
  --model-dir   Path to INT8 quantized ONNX model directory
  --host        Listen address (default: 0.0.0.0)
  --port        Listen port (default: 6006)
  --batch-size  Max texts per request (default: 32)
  --device      cpu or cuda (default: cpu for edge)
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = os.getenv(
    "EDGE_EMBED_MODEL_DIR",
    "models/bge-m3-onnx/quantized_int8",
)
DEFAULT_PORT = int(os.getenv("EDGE_EMBED_PORT", "6006"))


class EdgeEmbedder:
    """Wraps INT8 ONNX model for CPU inference."""

    def __init__(self, model_dir: str, device: str = "cpu") -> None:
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer
        except ImportError:
            raise RuntimeError("pip install onnxruntime transformers")

        model_path = Path(model_dir)
        onnx_file = next(model_path.glob("*.onnx"), None)
        if onnx_file is None:
            raise FileNotFoundError(f"No .onnx file found in {model_dir}")

        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if device == "cuda"
            else ["CPUExecutionProvider"]
        )
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = os.cpu_count() or 4
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        self._session = ort.InferenceSession(
            str(onnx_file), sess_options=sess_options, providers=providers
        )
        # Tokenizer loads from model_dir or falls back to parent directory
        tok_dir = model_dir if (Path(model_dir) / "tokenizer_config.json").exists() else str(Path(model_dir).parent)
        self._tokenizer = AutoTokenizer.from_pretrained(tok_dir, local_files_only=True)
        log.info("EdgeEmbedder loaded: %s (%s)", onnx_file.name, device)

    def embed(self, texts: list[str], max_length: int = 512) -> list[list[float]]:
        """Return L2-normalised embeddings for a batch of texts."""
        import numpy as np

        enc = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="np",
        )
        inputs = {k: v.astype(np.int64) for k, v in enc.items()
                  if k in ("input_ids", "attention_mask", "token_type_ids")}
        outputs = self._session.run(None, inputs)

        # CLS pooling (first token) — matches BGE-M3 convention
        hidden = outputs[0][:, 0, :]  # (batch, hidden)
        norms = np.linalg.norm(hidden, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-9)
        return (hidden / norms).tolist()


def build_app(embedder: EdgeEmbedder, max_batch: int):
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
    except ImportError:
        raise RuntimeError("pip install fastapi uvicorn")

    app = FastAPI(
        title="Aviation Edge Embedding Server",
        description="Offline INT8 ONNX embedding inference for factory-floor devices",
        version="1.0.0",
    )

    class EmbedRequest(BaseModel):
        texts: list[str]
        max_length: int = 512

    class EmbedResponse(BaseModel):
        embeddings: list[list[float]]
        model: str = "bge-m3-int8-onnx"
        latency_ms: float

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "mode": "offline-edge"}

    @app.post("/embed", response_model=EmbedResponse)
    def embed(req: EmbedRequest) -> EmbedResponse:
        if not req.texts:
            raise HTTPException(400, "texts must not be empty")
        if len(req.texts) > max_batch:
            raise HTTPException(400, f"batch size exceeds limit ({max_batch})")
        t0 = time.perf_counter()
        vecs = embedder.embed(req.texts, max_length=req.max_length)
        ms = (time.perf_counter() - t0) * 1000
        return EmbedResponse(embeddings=vecs, latency_ms=round(ms, 2))

    # OpenAI-compatible endpoint so existing clients work without changes
    @app.post("/v1/embeddings")
    def openai_compat(body: dict[str, Any]) -> dict[str, Any]:
        texts = body.get("input", [])
        if isinstance(texts, str):
            texts = [texts]
        t0 = time.perf_counter()
        vecs = embedder.embed(texts)
        ms = (time.perf_counter() - t0) * 1000
        return {
            "object": "list",
            "data": [
                {"object": "embedding", "index": i, "embedding": v}
                for i, v in enumerate(vecs)
            ],
            "model": "bge-m3-int8-onnx",
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
            "_latency_ms": round(ms, 2),
        }

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    args = parser.parse_args()

    embedder = EdgeEmbedder(args.model_dir, device=args.device)
    app = build_app(embedder, max_batch=args.batch_size)

    try:
        import uvicorn
    except ImportError:
        raise RuntimeError("pip install uvicorn")

    log.info(
        "Edge embedding server starting on http://%s:%d (batch_max=%d, device=%s)",
        args.host, args.port, args.batch_size, args.device,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
