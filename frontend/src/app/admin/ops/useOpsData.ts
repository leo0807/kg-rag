"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";

export interface Overview {
  knowledge: { documents: number; sections: number; images: number; drawings: number };
  quality: { retrieval_cases: number; negative_feedback_7d: number; audit_events_7d: number };
  runtime: { total: number; running: number; failed: number; queued: number; completed: number };
  recent_audits: { id: number; action: string; resource: string; detail: string; username: string; created_at: string }[];
}

export interface RuntimeItem {
  source: string; task_type: string; task_id: string; label: string;
  status: string; progress: number; total: number; completed: number;
  current: string; message: string; updated_at: string;
}

export interface HarnessResult {
  question: string;
  answer: string;
  plan: { strategy: string; reason: string; doc_id: string; intents: string[]; steps: { tool: string; description: string }[] };
  runtime: { strategy: string; top_k: number; section_hits: number; image_hits: number; drawing_only: boolean; warnings: string[]; retrieval_trace_counts: Record<string, number> };
  section_sources: { chunk_id: string; doc_id: string; number: string; title: string; score: number; retrieval_trace: string[]; source_type: string[]; content: string }[];
  image_sources: { image_id: string; doc_id: string; summary: string; caption: string; is_drawing: boolean; section_number?: string; section_title?: string; keyword_hits: number; url?: string | null }[];
}

export interface RetrievalBaselineTask {
  task_id: string; filename: string;
  status: "queued" | "running" | "completed" | "failed";
  total: number; completed: number; matched: number; unmatched: number;
  current_question: string;
  summary: { total: number; matched: number; unmatched: number; hit_rate: number; avg_recall: number; mrr: number } | null;
  error: string;
}

export function useOpsData() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [runtimeItems, setRuntimeItems] = useState<RuntimeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const loadOverview = useCallback(async () => {
    const [overviewData, runtimeData] = await Promise.all([
      fetchApi<Overview>("/api/admin/ops/overview"),
      fetchApi<{ items: RuntimeItem[] }>("/api/admin/ops/runtime?limit=12"),
    ]);
    setOverview(overviewData);
    setRuntimeItems(runtimeData.items);
  }, []);

  const refresh = useCallback(async () => {
    try {
      setRefreshing(true);
      setError(null);
      await loadOverview();
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载工程台失败");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [loadOverview]);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 10000);
    return () => {
      window.clearInterval(timer);
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [refresh]);

  return { overview, runtimeItems, loading, refreshing, error, setError, loadOverview, refresh, pollRef };
}
