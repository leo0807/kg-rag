import type { PipelineEdge, PipelineNode } from "./types";

function node(
  id: string,
  nodeType: string,
  label: string,
  category: string,
  color: string,
  inputs: string[],
  outputs: string[],
  params: Record<string, number | string>,
  x: number,
  y: number,
): PipelineNode {
  return {
    id,
    type: "pipelineNode",
    position: { x, y },
    data: { nodeType, label, color, category, inputs, outputs, params },
  };
}

function edge(
  id: string,
  source: string,
  target: string,
  sourceHandle: string,
  targetHandle: string,
): PipelineEdge {
  return {
    id,
    source,
    target,
    sourceHandle,
    targetHandle,
    animated: true,
    style: { stroke: "#6366f1" },
  };
}

export const PRESETS: Record<string, { label: string; nodes: PipelineNode[]; edges: PipelineEdge[] }> = {
  parallel_rrf: {
    label: "并行RRF（默认）",
    nodes: [
      node("vec1", "vector_search", "向量检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { top_k: 10 }, 80, 90),
      node("bm1", "bm25_search", "全文检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { top_k: 10 }, 80, 250),
      node("rrf1", "rrf_fusion", "RRF融合", "processing", "#5A9E28", ["candidates"], ["candidates"], { k: 60 }, 340, 170),
      node("rrk1", "rerank", "Rerank", "processing", "#5A9E28", ["query", "candidates"], ["candidates"], { top_k: 5 }, 580, 170),
      node("llm1", "llm_generate", "LLM生成", "generation", "#D4820A", ["query", "candidates"], ["answer"], { max_tokens: 1000, temperature: 0.1 }, 820, 170),
    ],
    edges: [
      edge("e1", "vec1", "rrf1", "candidates", "candidates"),
      edge("e2", "bm1", "rrf1", "candidates", "candidates"),
      edge("e3", "rrf1", "rrk1", "candidates", "candidates"),
      edge("e4", "rrk1", "llm1", "candidates", "candidates"),
    ],
  },
  graph_enhanced: {
    label: "图谱增强",
    nodes: [
      node("vec1", "vector_search", "向量检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { top_k: 12 }, 80, 120),
      node("gex1", "graph_expand", "图谱扩展", "processing", "#5A9E28", ["candidates"], ["candidates"], { hops: 2 }, 340, 120),
      node("rrk1", "rerank", "Rerank", "processing", "#5A9E28", ["query", "candidates"], ["candidates"], { top_k: 5 }, 580, 120),
      node("llm1", "llm_generate", "LLM生成", "generation", "#D4820A", ["query", "candidates"], ["answer"], { max_tokens: 1000, temperature: 0.1 }, 820, 120),
    ],
    edges: [
      edge("e1", "vec1", "gex1", "candidates", "candidates"),
      edge("e2", "gex1", "rrk1", "candidates", "candidates"),
      edge("e3", "rrk1", "llm1", "candidates", "candidates"),
    ],
  },
  multi_hop: {
    label: "多跳推理",
    nodes: [
      node("vec1", "vector_search", "向量检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { top_k: 12 }, 80, 120),
      node("hop1", "graph_expand", "多跳", "processing", "#5A9E28", ["candidates"], ["candidates"], { hops: 2 }, 340, 60),
      node("hop2", "graph_expand", "图谱扩展", "processing", "#5A9E28", ["candidates"], ["candidates"], { hops: 1 }, 580, 120),
      node("llm1", "llm_generate", "LLM生成", "generation", "#D4820A", ["query", "candidates"], ["answer"], { max_tokens: 1200, temperature: 0.1 }, 820, 120),
    ],
    edges: [
      edge("e1", "vec1", "hop1", "candidates", "candidates"),
      edge("e2", "hop1", "hop2", "candidates", "candidates"),
      edge("e3", "hop2", "llm1", "candidates", "candidates"),
    ],
  },
  es_hybrid: {
    label: "ES混合检索",
    nodes: [
      node("vec1", "vector_search", "向量检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { top_k: 10 }, 80, 90),
      node("bm1", "bm25_search", "全文检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { top_k: 10 }, 80, 250),
      node("rrf1", "rrf_fusion", "RRF融合", "processing", "#5A9E28", ["candidates"], ["candidates"], { k: 60, alpha: 0.5, alpha_source: "redis", alpha_redis_key: "search:hybrid_alpha" }, 340, 170),
      node("llm1", "llm_generate", "LLM生成", "generation", "#D4820A", ["query", "candidates"], ["answer"], { max_tokens: 1000, temperature: 0.1 }, 580, 170),
    ],
    edges: [
      edge("e1", "vec1", "rrf1", "candidates", "candidates"),
      edge("e2", "bm1", "rrf1", "candidates", "candidates"),
      edge("e3", "rrf1", "llm1", "candidates", "candidates"),
    ],
  },
  agent: {
    label: "Agent模式",
    nodes: [
      node("hyde1", "hyde", "HyDE增强", "processing", "#5A9E28", ["query"], ["query"], { alpha: 0.5 }, 70, 140),
      node("vec1", "vector_search", "向量检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { top_k: 12 }, 300, 60),
      node("gph1", "graph_search", "图谱检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { depth: 2, top_k: 10 }, 300, 220),
      node("rrf1", "rrf_fusion", "RRF融合", "processing", "#5A9E28", ["candidates"], ["candidates"], { k: 60 }, 540, 140),
      node("rrk1", "rerank", "Rerank", "processing", "#5A9E28", ["query", "candidates"], ["candidates"], { top_k: 5 }, 760, 140),
      node("rag1", "self_rag", "Self-RAG", "generation", "#D4820A", ["query", "candidates"], ["answer"], { max_iterations: 3 }, 980, 140),
    ],
    edges: [
      edge("e1", "hyde1", "vec1", "query", "query"),
      edge("e2", "hyde1", "gph1", "query", "query"),
      edge("e3", "vec1", "rrf1", "candidates", "candidates"),
      edge("e4", "gph1", "rrf1", "candidates", "candidates"),
      edge("e5", "rrf1", "rrk1", "candidates", "candidates"),
      edge("e6", "rrk1", "rag1", "candidates", "candidates"),
    ],
  },
};
