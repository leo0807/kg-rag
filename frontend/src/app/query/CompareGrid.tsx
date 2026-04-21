"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { CompareResult } from "./useCompareQuery";

const STRATEGY_RING: Record<string, string> = {
    parallel:        "border-indigo-700/50  text-indigo-400",
    sequential:      "border-emerald-700/50 text-emerald-400",
    graph_augmented: "border-amber-700/50   text-amber-400",
    multi_hop:       "border-purple-700/50  text-purple-400",
};

const STRATEGY_BG: Record<string, string> = {
    parallel:        "bg-indigo-950/20",
    sequential:      "bg-emerald-950/20",
    graph_augmented: "bg-amber-950/20",
    multi_hop:       "bg-purple-950/20",
};

const ERROR_LABELS: Record<string, string> = {
    quota_exceeded:      "额度不足",
    rate_limited:        "频率限制",
    timeout:             "响应超时",
    service_unavailable: "服务不可用",
    unknown_error:       "服务异常",
};

const SKELETON_STRATEGIES = [
    { strategy: "parallel",        label: "并行检索" },
    { strategy: "sequential",      label: "顺序检索" },
    { strategy: "graph_augmented", label: "图谱增强" },
    { strategy: "multi_hop",       label: "多跳推理" },
];

interface Props {
    question:        string;
    results:         CompareResult[];
    loading:         boolean;
    retryingStrategy: string | null;
    onUseAnswer:     (answer: string, strategy: string) => void;
    onRetryStrategy: (strategy: string) => void;
}

export default function CompareGrid({
    question, results, loading, retryingStrategy, onUseAnswer, onRetryStrategy,
}: Props) {
    const items = loading
        ? SKELETON_STRATEGIES.map(s => ({
            ...s, answer: null, sources: [], latency_ms: 0, error: null,
          }))
        : results;

    if (!loading && results.length === 0) return null;

    return (
        <div className="flex flex-col gap-3 mt-2">
            <div className="text-xs text-gray-500 px-1">
                对比问题：<span className="text-gray-300">{question}</span>
            </div>
            <div className="grid grid-cols-2 gap-3">
                {items.map(r => {
                    const ringCls = STRATEGY_RING[r.strategy] ?? "border-gray-700 text-gray-400";
                    const bgCls   = STRATEGY_BG[r.strategy]   ?? "bg-gray-900/20";
                    const isRetrying = retryingStrategy === r.strategy;
                    const hasError   = !!r.error;

                    return (
                        <div
                            key={r.strategy}
                            className={`flex flex-col rounded-xl border overflow-hidden
                                ${hasError ? "border-red-700/50 bg-red-950/20" : `${ringCls} ${bgCls}`}`}
                        >
                            {/* Header */}
                            <div className={`flex items-center justify-between px-3 py-2 border-b
                                ${hasError ? "border-red-700/40 text-red-400" : `border-current ${ringCls}`}`}>
                                <div className="flex items-center gap-1.5">
                                    <span className="text-xs font-semibold">{r.label || r.strategy}</span>
                                    {hasError && (
                                        <span className="text-[10px] px-1.5 py-0.5 bg-red-900/50 border border-red-700/50 rounded text-red-400">
                                            {ERROR_LABELS[r.error!.code] ?? "失败"}
                                        </span>
                                    )}
                                </div>
                                {!loading && !hasError && r.latency_ms > 0 && (
                                    <span className="text-[10px] text-gray-500">
                                        {(r.latency_ms / 1000).toFixed(1)}s
                                    </span>
                                )}
                            </div>

                            {/* Body */}
                            <div className="flex-1 overflow-auto max-h-72 px-3 py-2">
                                {loading || isRetrying ? (
                                    <div className="flex flex-col gap-2 animate-pulse">
                                        <div className="h-2.5 bg-gray-800 rounded w-full" />
                                        <div className="h-2.5 bg-gray-800 rounded w-5/6" />
                                        <div className="h-2.5 bg-gray-800 rounded w-4/6" />
                                        <div className="h-2.5 bg-gray-800 rounded w-full" />
                                        <div className="h-2.5 bg-gray-800 rounded w-3/4" />
                                    </div>
                                ) : hasError ? (
                                    <div className="flex flex-col gap-2">
                                        <div className="flex items-start gap-1.5">
                                            <AlertTriangle size={13} className="text-red-400 mt-0.5 shrink-0" />
                                            <p className="text-xs text-red-300">{r.error!.message}</p>
                                        </div>
                                        {r.error!.status_code && (
                                            <p className="text-[10px] text-red-400/60 font-mono">
                                                HTTP {r.error!.status_code}
                                            </p>
                                        )}
                                    </div>
                                ) : (
                                    <div className="text-xs text-gray-300 leading-relaxed
                                                    prose prose-invert prose-xs max-w-none
                                                    prose-p:text-gray-300 prose-p:leading-relaxed
                                                    prose-strong:text-gray-100
                                                    prose-code:text-indigo-300 prose-code:text-[10px]">
                                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                            {r.answer ?? "（无结果）"}
                                        </ReactMarkdown>
                                    </div>
                                )}
                            </div>

                            {/* Footer */}
                            {!loading && !isRetrying && (
                                <div className={`flex items-center justify-between px-3 py-1.5 border-t
                                    ${hasError ? "border-red-800/40" : "border-gray-800/50"}`}>
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <span className="text-[10px] text-gray-600">
                                            {hasError ? "—" : `${r.sources.length} 个来源`}
                                        </span>
                                        {!hasError && r.sources.some(s => s.rerank_score !== undefined) && (
                                            <div className="flex gap-1 flex-wrap">
                                                {r.sources.slice(0, 3).map((s, i) => {
                                                    const rs = s.rerank_score ?? 0;
                                                    const color = rs >= 0.8
                                                        ? "text-emerald-400 border-emerald-700/50"
                                                        : rs >= 0.5
                                                        ? "text-amber-400 border-amber-700/50"
                                                        : "text-gray-500 border-gray-700/50";
                                                    return (
                                                        <span
                                                            key={i}
                                                            title={`相关性分数：${rs.toFixed(2)}`}
                                                            className={`text-[9px] px-1 py-0.5 border rounded font-mono ${color}`}
                                                        >
                                                            {rs.toFixed(2)}
                                                        </span>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        {/* 重试按钮（失败和成功都可用） */}
                                        <button
                                            onClick={() => onRetryStrategy(r.strategy)}
                                            title="单独重试此策略"
                                            className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded border transition-colors
                                                ${hasError
                                                    ? "border-red-600/50 text-red-400 hover:bg-red-900/30"
                                                    : "border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-500"}`}
                                        >
                                            <RefreshCw size={9} />
                                            重试
                                        </button>
                                        {/* 使用此答案（仅成功时） */}
                                        {!hasError && r.answer && (
                                            <button
                                                onClick={() => onUseAnswer(r.answer!, r.strategy)}
                                                className={`text-[10px] px-2 py-0.5 rounded border transition-opacity hover:opacity-80 ${ringCls}`}
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
