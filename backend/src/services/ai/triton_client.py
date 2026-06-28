"""
Triton Inference Server gRPC client.

Provides:
  TritonClient            — thin async wrapper around tritonclient.grpc
  get_triton_client()     — cached singleton
  embed_bge_m3()          — BGE-M3 embedding via Triton
  rerank_bge_reranker()   — bge-reranker cross-encoder scores via Triton
  infer_gnn()             — GNN node-embedding inference via Triton

All functions degrade gracefully: if Triton is unavailable or tritonclient is
not installed, they raise TritonUnavailable so callers can fall back.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

_TRITON_URL  = os.getenv("TRITON_GRPC_URL", "localhost:8001")
_BATCH_LIMIT = int(os.getenv("TRITON_MAX_BATCH", "32"))


class TritonUnavailable(RuntimeError):
    """Raised when Triton cannot be reached or is not installed."""


@dataclass
class TritonClient:
    url: str

    def _client(self):
        try:
            import tritonclient.grpc as tc  # type: ignore
            return tc
        except ImportError as exc:
            raise TritonUnavailable("tritonclient not installed") from exc

    def _conn(self):
        tc = self._client()
        return tc.InferenceServerClient(url=self.url)

    def is_live(self) -> bool:
        try:
            return self._conn().is_server_live()
        except Exception:
            return False

    # ------------------------------------------------------------------
    # BGE-M3  (embedding)
    # ------------------------------------------------------------------

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return float32 embeddings, shape (N, D)."""
        tc = self._client()
        conn = self._conn()
        all_vectors: list[np.ndarray] = []
        for i in range(0, len(texts), _BATCH_LIMIT):
            batch = texts[i : i + _BATCH_LIMIT]
            inp = tc.InferInput("TEXT", [len(batch), 1], "BYTES")
            inp.set_data_from_numpy(
                np.array([[t.encode()] for t in batch], dtype=object)
            )
            out = tc.InferRequestedOutput("EMBEDDING")
            result = conn.infer(model_name="bge-m3", inputs=[inp], outputs=[out])
            all_vectors.append(result.as_numpy("EMBEDDING"))
        return np.vstack(all_vectors)

    # ------------------------------------------------------------------
    # BGE-Reranker  (cross-encoder)
    # ------------------------------------------------------------------

    def rerank(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Return relevance scores for (query, passage) pairs."""
        tc = self._client()
        conn = self._conn()
        scores: list[float] = []
        for i in range(0, len(pairs), _BATCH_LIMIT):
            batch = pairs[i : i + _BATCH_LIMIT]
            n = len(batch)
            inp_q = tc.InferInput("QUERY",   [n, 1], "BYTES")
            inp_p = tc.InferInput("PASSAGE", [n, 1], "BYTES")
            inp_q.set_data_from_numpy(np.array([[p[0].encode()] for p in batch], dtype=object))
            inp_p.set_data_from_numpy(np.array([[p[1].encode()] for p in batch], dtype=object))
            out = tc.InferRequestedOutput("SCORE")
            result = conn.infer(model_name="bge-reranker", inputs=[inp_q, inp_p], outputs=[out])
            scores.extend(result.as_numpy("SCORE").flatten().tolist())
        return scores

    # ------------------------------------------------------------------
    # GNN node embeddings
    # ------------------------------------------------------------------

    def gnn_embed(self, node_features: np.ndarray) -> np.ndarray:
        """
        Forward-pass node features through GNN model on Triton.

        node_features: shape (N, F) float32
        returns: shape (N, D) float32 graph embeddings
        """
        tc = self._client()
        conn = self._conn()
        n, f = node_features.shape
        inp = tc.InferInput("NODE_FEAT", [n, f], "FP32")
        inp.set_data_from_numpy(node_features.astype(np.float32))
        out = tc.InferRequestedOutput("NODE_EMBED")
        result = conn.infer(model_name="gnn", inputs=[inp], outputs=[out])
        return result.as_numpy("NODE_EMBED")

    # ------------------------------------------------------------------
    # Entity extraction LLM
    # ------------------------------------------------------------------

    def extract_entities(self, text: str) -> str:
        """
        Run entity extraction LLM on Triton (deployed as a tokenised
        sequence model). Returns raw JSON string from the model.
        """
        tc = self._client()
        conn = self._conn()
        inp = tc.InferInput("TEXT", [1, 1], "BYTES")
        inp.set_data_from_numpy(np.array([[text.encode()]], dtype=object))
        out = tc.InferRequestedOutput("RESULT")
        result = conn.infer(model_name="entity-extract-llm", inputs=[inp], outputs=[out])
        raw = result.as_numpy("RESULT")
        return raw.flatten()[0].decode()


@lru_cache(maxsize=1)
def get_triton_client() -> TritonClient:
    return TritonClient(url=_TRITON_URL)


# ---------------------------------------------------------------------------
# Async helper wrappers
# ---------------------------------------------------------------------------

async def embed_bge_m3(texts: list[str]) -> np.ndarray:
    return await asyncio.to_thread(get_triton_client().embed, texts)


async def rerank_bge_reranker(pairs: list[tuple[str, str]]) -> list[float]:
    return await asyncio.to_thread(get_triton_client().rerank, pairs)


async def infer_gnn(node_features: np.ndarray) -> np.ndarray:
    return await asyncio.to_thread(get_triton_client().gnn_embed, node_features)


async def extract_entities_triton(text: str) -> str:
    return await asyncio.to_thread(get_triton_client().extract_entities, text)
