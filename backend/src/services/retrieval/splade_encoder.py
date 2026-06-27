"""
SPLADE sparse vector encoder for aviation terminology.

Model: naver/splade-cocondenser-selfdistil
Output: sparse dict {token: weight} indexed into Elasticsearch sparse_vector field.

SPLADE advantages over BM25 for aviation:
- OOV terms like "CRES 钢", "HB5292" are expanded via BERT vocabulary
- Query expansion: "扭矩" → also matches "力矩", "N·m", "torque"
- Sparse, interpretable (unlike dense vectors)

Usage:
    from .splade_encoder import SpladeEncoder
    enc = SpladeEncoder()
    sparse_vec = enc.encode_single("液压管路安装规范")
    # → {"liquid": 2.1, "hydraulic": 1.8, "install": 1.5, ...}

Indexing sections:
    enc.index_sections(section_list, es_client)

Requires:
    pip install transformers torch
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

log = logging.getLogger(__name__)

MODEL_NAME = os.getenv("SPLADE_MODEL", "naver/splade-cocondenser-selfdistil")
MAX_LENGTH = int(os.getenv("SPLADE_MAX_LENGTH", "256"))


class SpladeEncoder:
    """Wraps SPLADE model for sparse vector generation."""

    def __init__(self, model_name: str = MODEL_NAME, device: str = "cpu") -> None:
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForMaskedLM
        except ImportError:
            raise RuntimeError("pip install transformers torch")

        self._device = device
        self._tok = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModelForMaskedLM.from_pretrained(model_name).to(device)
        self._model.eval()
        log.info("SPLADE loaded: %s on %s", model_name, device)

    def encode_single(self, text: str) -> dict[str, float]:
        """Return {token_string: weight} sparse representation."""
        import torch
        inputs = self._tok(
            text,
            return_tensors="pt",
            max_length=MAX_LENGTH,
            truncation=True,
            padding=True,
        ).to(self._device)

        with torch.no_grad():
            logits = self._model(**inputs).logits  # (1, seq_len, vocab)
            # SPLADE aggregation: max over sequence, ReLU, log(1+x)
            agg = torch.log1p(torch.relu(logits)).max(dim=1).values.squeeze(0)

        token_ids = agg.nonzero(as_tuple=True)[0].cpu().tolist()
        weights   = agg[token_ids].cpu().tolist()

        # Map token_ids → token strings (skip special tokens)
        vocab = self._tok.convert_ids_to_tokens(token_ids)
        result: dict[str, float] = {}
        for tok, w in zip(vocab, weights):
            if tok and not tok.startswith("[") and w > 0.01:
                result[tok] = round(float(w), 4)
        return result

    def encode_batch(self, texts: list[str]) -> list[dict[str, float]]:
        return [self.encode_single(t) for t in texts]

    def index_sections(
        self,
        sections: list[dict[str, Any]],
        es,
        index_name: str = "cps_sections",
        batch_size: int = 32,
    ) -> int:
        """Encode sections and update their sparse_vector field in ES."""
        from elasticsearch.helpers import bulk as es_bulk

        total = 0
        for i in range(0, len(sections), batch_size):
            batch = sections[i : i + batch_size]
            texts = [s.get("content") or s.get("title") or "" for s in batch]
            sparse_vecs = self.encode_batch(texts)

            actions = [
                {
                    "_op_type": "update",
                    "_index":   index_name,
                    "_id":      s["chunk_id"],
                    "doc":      {"splade_vector": vec},
                    "doc_as_upsert": True,
                }
                for s, vec in zip(batch, sparse_vecs)
                if s.get("chunk_id")
            ]
            success, _ = es_bulk(es, actions, raise_on_error=False)
            total += success
            log.info("SPLADE indexed %d/%d sections", total, len(sections))

        return total


def splade_search(
    query: str,
    es,
    top_k: int = 10,
    index_name: str = "cps_sections",
) -> list[dict[str, Any]]:
    """
    Query OpenSearch using SPLADE sparse_vector field.
    Falls back to BM25 text search if sparse_vector field is absent.
    """
    enc = _get_encoder()
    sparse_q = enc.encode_single(query)

    # Build sparse_vector query (ES 8.11+ / OpenSearch 2.x)
    try:
        resp = es.search(
            index=index_name,
            body={
                "size": top_k,
                "query": {
                    "sparse_vector": {
                        "field":       "splade_vector",
                        "query_vector": sparse_q,
                    }
                },
                "_source": ["chunk_id", "doc_id", "number", "title", "content"],
            },
        )
        hits = resp["hits"]["hits"]
    except Exception as exc:
        log.warning("sparse_vector query failed (%s), falling back to BM25", exc)
        resp = es.search(
            index=index_name,
            body={
                "size": top_k,
                "query": {"multi_match": {"query": query, "fields": ["title^2", "content"]}},
            },
        )
        hits = resp["hits"]["hits"]

    return [
        {**h["_source"], "score": h["_score"], "method": "splade"}
        for h in hits
    ]


@lru_cache(maxsize=1)
def _get_encoder() -> SpladeEncoder:
    device = "cuda" if _cuda_available() else "cpu"
    return SpladeEncoder(device=device)


def _cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False
