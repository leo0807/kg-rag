export interface SourceSection {
  chunk_id: string;
  doc_id: string;
  number: string;
  title: string;
  score: number;
  rerank_score?: number;
  page_idx?: number;
  bbox?: [number, number, number, number];
  source_type?: string[];
  retrieval_trace?: string[];
  is_graph_expanded?: boolean;
  is_vector_hit?: boolean;
  is_fulltext_hit?: boolean;
  is_gnn_hit?: boolean;
  // table row
  content_type?: string;
  table_id?: string;
  row_index?: number;
  headers?: string[];
  row_data?: Record<string, string>;
}

export type SourceFilterType = "fulltext" | "vector" | "graph" | "gnn";

export interface SourcePanelFilters {
  sourceTypes: SourceFilterType[];
  expandedOnly: boolean;
  traceFilters: string[];
}

export interface LLMErrorInfo {
  code: string;
  message: string;
  status_code: number | null;
  endpoint: string;
}

export interface ClarificationInfo {
  message: string;
  options: string[];
  originalQuestion: string;
}

export interface AgentStepInfo {
  step: number;
  action: string;
  status: "running" | "done" | "failed";
  input?: unknown;
  result_summary?: string;
}

export interface QueryMetrics {
  total_ms: number;
  stages: Record<string, number>;
  tokens: Record<string, number>;
  cost_usd: number;
  candidates_retrieved: number;
  candidates_after_rerank: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceSection[];
  images?: string[]; // base64 data URIs (user messages only)
  causalChain?: CausalChainData;
  followUpQuestions?: string[];
  errorInfo?: LLMErrorInfo;
  expansionInfo?: string[];
  metrics?: QueryMetrics;
  clarification?: ClarificationInfo;
  agentSteps?: AgentStepInfo[];
  timestamp: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  timestamp: number;
}

export type Strategy =
  | "parallel"
  | "sequential"
  | "graph_augmented"
  | "multi_hop"
  | "agent"
  | "counterfactual";

// ── 反事实因果链数据结构 ──────────────────────────────────────────
export interface CausalConstraint {
  type: string;
  value: string;
  value_max?: string;
  unit: string;
  description: string;
}

export interface CausalSection {
  chunk_id: string;
  number: string;
  title: string;
  doc_id: string;
  rel_type: string;
  rel_type_cn: string;
  constraints: CausalConstraint[];
  page_idx?: number;
  bbox?: [number, number, number, number];
}

export interface CausalChainData {
  entity_name: string;
  entity_type: string;
  affected_sections: CausalSection[];
  constraints: CausalConstraint[];
  alternatives: string[];
  intent: {
    removed_type: string;
    removed_name: string;
    subject: string;
    requirement: string;
  };
}
