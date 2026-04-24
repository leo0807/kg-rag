"use client";

import { useState } from "react";
import { fetchApi } from "@/lib/api";
import type { LLMErrorInfo, SourceSection } from "./types";

export interface CompareResult {
  strategy: string;
  label: string;
  answer: string | null;
  sources: SourceSection[];
  latency_ms: number;
  error: LLMErrorInfo | null;
}

interface CompareState {
  loading: boolean;
  retryingStrategy: string | null;
  question: string;
  results: CompareResult[];
}

export function useCompareQuery() {
  const [state, setState] = useState<CompareState>({
    loading: false,
    retryingStrategy: null,
    question: "",
    results: [],
  });

  async function compare(question: string) {
    if (!question.trim()) return;
    setState({ loading: true, retryingStrategy: null, question, results: [] });
    try {
      const data = await fetchApi<{ results?: CompareResult[] }>(
        "/api/query/compare",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, strategy: "parallel" }),
        },
      );
      setState({
        loading: false,
        retryingStrategy: null,
        question,
        results: data.results ?? [],
      });
    } catch (e) {
      setState((prev) => ({ ...prev, loading: false }));
      console.error("compare failed:", e);
    }
  }

  async function retryStrategy(strategy: string) {
    const { question } = state;
    if (!question.trim()) return;
    setState((prev) => ({ ...prev, retryingStrategy: strategy }));
    try {
      const data = await fetchApi<{ results?: CompareResult[] }>(
        "/api/query/compare",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question, strategy }),
        },
      );
      const newResult: CompareResult | undefined = (data.results ?? []).find(
        (r: CompareResult) => r.strategy === strategy,
      );
      if (newResult) {
        setState((prev) => ({
          ...prev,
          retryingStrategy: null,
          results: prev.results.map((r) =>
            r.strategy === strategy ? newResult : r,
          ),
        }));
      } else {
        setState((prev) => ({ ...prev, retryingStrategy: null }));
      }
    } catch (e) {
      setState((prev) => ({ ...prev, retryingStrategy: null }));
      console.error("retry strategy failed:", e);
    }
  }

  return { ...state, compare, retryStrategy };
}
