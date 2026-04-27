from __future__ import annotations

_SOURCE_TYPE_ORDER = {
    "fulltext": 0,
    "vector": 1,
    "graph": 2,
    "gnn": 3,
    "es_hybrid": 4,
}


def _ensure_source_meta(source_meta: dict[str, dict], chunk_id: str) -> dict:
    meta = source_meta.get(chunk_id)
    if meta is None:
        meta = {
            "source_type": set(),
            "retrieval_trace": [],
            "is_graph_expanded": False,
            "is_vector_hit": False,
            "is_fulltext_hit": False,
            "is_gnn_hit": False,
        }
        source_meta[chunk_id] = meta
    return meta


def _mark_sources(
    source_meta: dict[str, dict],
    chunk_ids: list[str],
    *,
    source_type: str | None = None,
    trace: str | None = None,
    is_graph_expanded: bool = False,
    is_vector_hit: bool = False,
    is_fulltext_hit: bool = False,
    is_gnn_hit: bool = False,
) -> None:
    for chunk_id in chunk_ids:
        if not chunk_id:
            continue
        meta = _ensure_source_meta(source_meta, chunk_id)
        if source_type:
            meta["source_type"].add(source_type)
        if trace and trace not in meta["retrieval_trace"]:
            meta["retrieval_trace"].append(trace)
        if is_graph_expanded:
            meta["is_graph_expanded"] = True
        if is_vector_hit:
            meta["is_vector_hit"] = True
        if is_fulltext_hit:
            meta["is_fulltext_hit"] = True
        if is_gnn_hit:
            meta["is_gnn_hit"] = True


def _finalize_source_meta(source_meta: dict[str, dict], chunk_id: str) -> dict:
    meta = source_meta.get(chunk_id) or {
        "source_type": set(),
        "retrieval_trace": [],
        "is_graph_expanded": False,
        "is_vector_hit": False,
        "is_fulltext_hit": False,
        "is_gnn_hit": False,
    }
    return {
        "source_type": sorted(
            list(meta["source_type"]),
            key=lambda item: _SOURCE_TYPE_ORDER.get(item, 99),
        ),
        "retrieval_trace": meta["retrieval_trace"],
        "is_graph_expanded": meta["is_graph_expanded"],
        "is_vector_hit": meta["is_vector_hit"],
        "is_fulltext_hit": meta["is_fulltext_hit"],
        "is_gnn_hit": meta["is_gnn_hit"],
    }
