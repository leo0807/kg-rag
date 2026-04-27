import type { PipelineEdge, PipelineNode } from "./types";

function node(id: string, nodeType: string, label: string, category: string, color: string, inputs: string[], outputs: string[], params: Record<string, number | string>, x: number, y: number): PipelineNode {
  return {
    id, type: "pipelineNode", position: { x, y },
    data: { nodeType, label, color, category, inputs, outputs, params },
  };
}

function edge(id: string, source: string, target: string, sourceHandle: string, targetHandle: string): PipelineEdge {
  return { id, source, target, sourceHandle, targetHandle, animated: true, style: { stroke: "#6366f1" } };
}

export const PRESETS: Record<string, { label: string; nodes: PipelineNode[]; edges: PipelineEdge[] }> = {
  fast: {
    label: "快速模式",
    nodes: [
      node("vec1", "vector_search", "向量检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { top_k: 10 }, 80, 150),
      node("llm1", "llm_generate", "LLM生成", "generation", "#D4820A", ["query", "candidates"], ["answer"], { max_tokens: 1000, temperature: 0.1 }, 380, 150),
    ],
    edges: [
      edge("e1", "vec1", "llm1", "candidates", "candidates"),
    ],
  },

  balanced: {
    label: "均衡模式",
    nodes: [
      node("vec1", "vector_search", "向量检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { top_k: 10 }, 80, 80),
      node("bm1",  "bm25_search",   "全文检索", "retrieval", "#1B6BB5", ["query"], ["candidates"], { top_k: 10 }, 80, 240),
      node("rrf1", "rrf_fusion",    "RRF融合",  "processing","#5A9E28", ["candidates"], ["candidates"], { k: 60 }, 340, 160),
      node("llm1", "llm_generate",  "LLM生成",  "generation","#D4820A", ["query", "candidates"], ["answer"], { max_tokens: 1000, temperature: 0.1 }, 600, 160),
    ],
    edges: [
      edge("e1", "vec1", "rrf1", "candidates", "candidates"),
      edge("e2", "bm1",  "rrf1", "candidates", "candidates"),
      edge("e3", "rrf1", "llm1", "candidates", "candidates"),
    ],
  },

  deep: {
    label: "深度模式",
    nodes: [
      node("vec1", "vector_search", "向量检索", "retrieval",  "#1B6BB5", ["query"], ["candidates"], { top_k: 15 }, 80, 80),
      node("gph1", "graph_search",  "图谱检索", "retrieval",  "#1B6BB5", ["query"], ["candidates"], { depth: 2, top_k: 10 }, 80, 260),
      node("rrf1", "rrf_fusion",    "RRF融合",  "processing", "#5A9E28", ["candidates"], ["candidates"], { k: 60 }, 340, 170),
      node("rrk1", "rerank",        "重排序",   "processing", "#5A9E28", ["query", "candidates"], ["candidates"], { top_k: 5 }, 580, 170),
      node("llm1", "llm_generate",  "LLM生成",  "generation", "#D4820A", ["query", "candidates"], ["answer"], { max_tokens: 1000, temperature: 0.1 }, 820, 170),
    ],
    edges: [
      edge("e1", "vec1", "rrf1", "candidates", "candidates"),
      edge("e2", "gph1", "rrf1", "candidates", "candidates"),
      edge("e3", "rrf1", "rrk1", "candidates", "candidates"),
      edge("e4", "rrk1", "llm1", "candidates", "candidates"),
    ],
  },

  expert: {
    label: "专家模式",
    nodes: [
      node("vec1", "vector_search", "向量检索", "retrieval",  "#1B6BB5", ["query"], ["candidates"], { top_k: 15 }, 80, 60),
      node("bm1",  "bm25_search",   "全文检索", "retrieval",  "#1B6BB5", ["query"], ["candidates"], { top_k: 10 }, 80, 200),
      node("gph1", "graph_search",  "图谱检索", "retrieval",  "#1B6BB5", ["query"], ["candidates"], { depth: 2, top_k: 10 }, 80, 340),
      node("rrf1", "rrf_fusion",    "RRF融合",  "processing", "#5A9E28", ["candidates"], ["candidates"], { k: 60 }, 340, 200),
      node("gex1", "graph_expand",  "图谱扩展", "processing", "#5A9E28", ["candidates"], ["candidates"], { hops: 1 }, 580, 120),
      node("rrk1", "rerank",        "重排序",   "processing", "#5A9E28", ["query", "candidates"], ["candidates"], { top_k: 5 }, 580, 280),
      node("llm1", "llm_generate",  "LLM生成",  "generation", "#D4820A", ["query", "candidates"], ["answer"], { max_tokens: 1500, temperature: 0.1 }, 840, 200),
    ],
    edges: [
      edge("e1", "vec1", "rrf1", "candidates", "candidates"),
      edge("e2", "bm1",  "rrf1", "candidates", "candidates"),
      edge("e3", "gph1", "rrf1", "candidates", "candidates"),
      edge("e4", "rrf1", "gex1", "candidates", "candidates"),
      edge("e5", "rrf1", "rrk1", "candidates", "candidates"),
      edge("e6", "gex1", "llm1", "candidates", "candidates"),
      edge("e7", "rrk1", "llm1", "candidates", "candidates"),
    ],
  },
};
