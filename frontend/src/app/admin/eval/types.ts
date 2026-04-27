export type Strategy =
  | "parallel"
  | "sequential"
  | "graph_augmented"
  | "multi_hop"
  | "counterfactual"
  | "gnn";

export type RetrievalStrategy =
  | "parallel"
  | "sequential"
  | "graph_augmented"
  | "gnn";

export type EvalTabKey = "dataset" | "objective" | "retrieval" | "faithfulness" | "ab_test";

export interface EvalRow {
  row_no: number;
  question: string;
  expected_answer: string;
  actual_answer: string;
  domain: string;
  matched: boolean;
  similarity: number;
  source_refs: string[];
}

export interface EvalTask {
  task_id: string;
  filename: string;
  status: "queued" | "running" | "completed" | "failed";
  strategy: Strategy;
  top_k: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  completed: number;
  passed: number;
  failed: number;
  current_question: string;
  error: string;
  summary: {
    total: number;
    passed: number;
    failed: number;
    pass_rate: number;
  } | null;
  results_preview: EvalRow[];
  results: EvalRow[];
}

export interface ObjectiveOption {
  label: string;
  text: string;
}

export interface ObjectiveRow {
  display_no: string;
  question: string;
  options: ObjectiveOption[];
  question_type: string;
  predicted_answer: string;
  reason: string;
  source_refs: string[];
}

export interface ObjectiveTask {
  task_id: string;
  filename: string;
  status: "queued" | "running" | "completed" | "failed";
  strategy: Strategy;
  top_k: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  completed: number;
  current_question: string;
  error: string;
  summary: { total: number; choice_count: number; judge_count: number } | null;
  results_preview: ObjectiveRow[];
  results: ObjectiveRow[];
}

export interface RetrievalRow {
  row_no: number;
  question: string;
  domain: string;
  strategy: RetrievalStrategy;
  target_type: "chunk" | "doc";
  gold_chunk_ids: string[];
  gold_doc_ids: string[];
  retrieved_chunk_ids: string[];
  retrieved_doc_ids: string[];
  matched: boolean;
  hit_rank: number | null;
  recall: number;
  reciprocal_rank: number;
  ndcg: number;
  source_refs: string[];
}

export interface RetrievalTask {
  task_id: string;
  filename: string;
  status: "queued" | "running" | "completed" | "failed";
  strategy: RetrievalStrategy;
  top_k: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  completed: number;
  matched: number;
  unmatched: number;
  current_question: string;
  error: string;
  summary: {
    total: number;
    matched: number;
    unmatched: number;
    hit_rate: number;
    avg_recall: number;
    mrr: number;
    avg_ndcg: number;
    chunk_target_count: number;
    doc_target_count: number;
  } | null;
  results_preview: RetrievalRow[];
  results: RetrievalRow[];
}

export interface FaithfulnessRow {
  row_no: number;
  question: string;
  answer: string;
  passages_count: number;
  faithful: boolean;
  score: number;
  unsupported_claims: string[];
  reason: string;
}

export interface FaithfulnessTask {
  task_id: string;
  filename: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  completed: number;
  faithful_count: number;
  current_question: string;
  error: string;
  summary: {
    total: number;
    faithful_count: number;
    unfaithful_count: number;
    faithfulness_rate: number;
    avg_score: number;
  } | null;
  results_preview: FaithfulnessRow[];
  results: FaithfulnessRow[];
}

export interface AbStrategySummary {
  strategy: string;
  total: number;
  matched: number;
  hit_rate: number;
  avg_recall: number;
  mrr: number;
  avg_ndcg: number;
}

export interface AbTestTask {
  task_id: string;
  filename: string;
  status: "queued" | "running" | "completed" | "failed";
  strategies: string[];
  top_k: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  total: number;
  completed: number;
  current_question: string;
  error: string;
  summary: {
    total_questions: number;
    strategies_compared: number;
    winner: string;
    details: AbStrategySummary[];
  } | null;
  strategy_summaries: (AbStrategySummary & { results: unknown[] })[];
}

export function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}
