"use client";

import { AlertTriangle, RefreshCw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AnswerImageGallery } from "./AnswerImageGallery";
import type { CompareResult } from "./useCompareQuery";

const STRATEGY_RING: Record<string, string> = {
  parallel: "border-indigo-700/50  text-indigo-400",
  sequential: "border-emerald-700/50 text-emerald-400",
  graph_augmented: "border-amber-700/50   text-amber-400",
  multi_hop: "border-purple-700/50  text-purple-400",
  hybrid_es: "border-orange-700/50  text-orange-400",
};

const STRATEGY_BG: Record<string, string> = {
  parallel: "bg-indigo-950/20",
  sequential: "bg-emerald-950/20",
  graph_augmented: "bg-amber-950/20",
  multi_hop: "bg-purple-950/20",
  hybrid_es: "bg-orange-950/20",
};

const ERROR_LABELS: Record<string, string> = {
  quota_exceeded: "额度不足",
  rate_limited: "频率限制",
  timeout: "响应超时",
  service_unavailable: "服务不可用",
  unknown_error: "服务异常",
};

const SKELETON_STRATEGIES = [
  { strategy: "parallel", label: "并行检索" },
  { strategy: "sequential", label: "顺序检索" },
  { strategy: "graph_augmented", label: "图谱增强" },
  { strategy: "multi_hop", label: "多跳推理" },
  { strategy: "hybrid_es", label: "ES 混合检索" },
];

interface Props {
  question: string;
  results: CompareResult[];
  loading: boolean;
  retryingStrategy: string | null;
  onUseAnswer: (answer: string, strategy: string) => void;
  onRetryStrategy: (strategy: string) => void;
}

export default function CompareGrid({
  question,
  results,
  loading,
  retryingStrategy,
  onUseAnswer,
  onRetryStrategy,
}: Props) {
  const items = loading
    ? SKELETON_STRATEGIES.map((s) => ({
        ...s,
        answer: null,
        sources: [],
        latency_ms: 0,
        error: null,
      }))
    : results;

  if (!loading && results.length === 0) return null;

  return (
    <div className="mt-2 flex flex-col gap-3">
      <div className="px-1 text-xs text-gray-500">
        对比问题：<span className="text-gray-300">{question}</span>
      </div>
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
        {items.map((r) => {
          const ringCls =
            STRATEGY_RING[r.strategy] ?? "border-gray-700 text-gray-400";
          const bgCls = STRATEGY_BG[r.strategy] ?? "bg-gray-900/20";
          const isRetrying = retryingStrategy === r.strategy;
          const hasError = !!r.error;
          const error = r.error;

          return (
            <div
              key={r.strategy}
              className={`flex flex-col overflow-hidden rounded-xl border
                ${hasError ? "border-red-700/50 bg-red-950/20" : `${ringCls} ${bgCls}`}`}
            >
              <div
                className={`flex items-center justify-between border-b px-3 py-2
                  ${hasError ? "border-red-700/40 text-red-400" : `border-current ${ringCls}`}`}
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-semibold">
                    {r.label || r.strategy}
                  </span>
                  {hasError && (
                    <span className="rounded border border-red-700/50 bg-red-900/50 px-1.5 py-0.5 text-[10px] text-red-400">
                      {ERROR_LABELS[error?.code ?? "unknown_error"] ?? "失败"}
                    </span>
                  )}
                </div>
                {!loading && !hasError && r.latency_ms > 0 && (
                  <span className="text-[10px] text-gray-500">
                    {(r.latency_ms / 1000).toFixed(1)}s
                  </span>
                )}
              </div>

              <div className="max-h-72 flex-1 overflow-auto px-3 py-2">
                {loading || isRetrying ? (
                  <div className="flex animate-pulse flex-col gap-2">
                    <div className="h-2.5 w-full rounded bg-gray-800" />
                    <div className="h-2.5 w-5/6 rounded bg-gray-800" />
                    <div className="h-2.5 w-4/6 rounded bg-gray-800" />
                    <div className="h-2.5 w-full rounded bg-gray-800" />
                    <div className="h-2.5 w-3/4 rounded bg-gray-800" />
                  </div>
                ) : hasError ? (
                  <div className="flex flex-col gap-2">
                    <div className="flex items-start gap-1.5">
                      <AlertTriangle
                        size={13}
                        className="mt-0.5 shrink-0 text-red-400"
                      />
                      <p className="text-xs text-red-300">{error?.message}</p>
                    </div>
                    {error?.status_code && (
                      <p className="font-mono text-[10px] text-red-400/60">
                        HTTP {error.status_code}
                      </p>
                    )}
                  </div>
                ) : (
                  <div
                    className="prose prose-xs max-w-none text-xs leading-relaxed
                               prose-invert prose-p:text-gray-300 prose-p:leading-relaxed
                               prose-strong:text-gray-100 prose-code:text-[10px] prose-code:text-indigo-300"
                  >
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {r.answer ?? "（无结果）"}
                    </ReactMarkdown>
                  </div>
                )}
                {!loading &&
                  !isRetrying &&
                  !hasError &&
                  r.images &&
                  r.images.length > 0 && (
                    <AnswerImageGallery
                      images={r.images}
                      limit={4}
                      title="相关图示"
                      contextText={r.answer ?? question}
                    />
                  )}
              </div>

              {!loading && !isRetrying && (
                <div
                  className={`flex items-center justify-between border-t px-3 py-1.5
                    ${hasError ? "border-red-800/40" : "border-gray-800/50"}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[10px] text-gray-600">
                      {hasError ? "—" : `${r.sources.length} 个来源`}
                    </span>
                    {!hasError &&
                      r.sources.some((s) => s.rerank_score !== undefined) && (
                        <div className="flex flex-wrap gap-1">
                          {r.sources.slice(0, 3).map((s) => {
                            const rs = s.rerank_score ?? 0;
                            const color =
                              rs >= 0.8
                                ? "text-emerald-400 border-emerald-700/50"
                                : rs >= 0.5
                                  ? "text-amber-400 border-amber-700/50"
                                  : "text-gray-500 border-gray-700/50";
                            return (
                              <span
                                key={`${s.chunk_id}-${s.doc_id}-${rs.toFixed(2)}`}
                                title={`相关性分数：${rs.toFixed(2)}`}
                                className={`rounded border px-1 py-0.5 font-mono text-[9px] ${color}`}
                              >
                                {rs.toFixed(2)}
                              </span>
                            );
                          })}
                        </div>
                      )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => onRetryStrategy(r.strategy)}
                      title="单独重试此策略"
                      className={`flex items-center gap-1 rounded border px-2 py-0.5 text-[10px] transition-colors
                        ${
                          hasError
                            ? "border-red-600/50 text-red-400 hover:bg-red-900/30"
                            : "border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-300"
                        }`}
                    >
                      <RefreshCw size={9} />
                      重试
                    </button>
                    {!hasError && r.answer && (
                      <button
                        type="button"
                        onClick={() => onUseAnswer(r.answer ?? "", r.strategy)}
                        className={`rounded border px-2 py-0.5 text-[10px] transition-opacity hover:opacity-80 ${ringCls}`}
                      >
                        使用此答案
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
