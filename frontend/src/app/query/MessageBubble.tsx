"use client";
import { AlertTriangle, ExternalLink, Reply, Star } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SourceGraph from "./SourceGraph";
import type {
  LLMErrorInfo,
  SourceFilterType,
  SourcePanelFilters,
  SourceSection,
} from "./types";

const RANK_COLORS = ["#fbbf24", "#34d399", "#60a5fa", "#f472b6", "#a78bfa"];
const SOURCE_LABELS: Record<string, string> = {
  fulltext: "全文",
  vector: "向量",
  graph: "图谱扩展",
  gnn: "GNN",
};
const SOURCE_FILTER_ORDER = ["fulltext", "vector", "graph", "gnn"] as const;
const DEFAULT_SOURCE_PANEL_FILTERS: SourcePanelFilters = {
  sourceTypes: [],
  expandedOnly: false,
  traceFilters: [],
};

const ERROR_HINTS: Record<string, string> = {
  quota_exceeded: "· 联系管理员充值或切换模型",
  rate_limited: "· 稍等片刻后重试",
  timeout: "· 点击重试，或换用响应更快的模型",
  service_unavailable: "· 检查 AI 服务是否正常运行",
  unknown_error: "· 联系管理员查看后端日志",
};

interface Props {
  role: "user" | "assistant";
  content: string;
  sources?: SourceSection[];
  images?: string[];
  streaming?: boolean;
  followUpQuestions?: string[];
  errorInfo?: LLMErrorInfo;
  isAdmin?: boolean;
  onSourceClick?: (chunkId: string) => void;
  onQuoteSource?: (source: SourceSection) => void;
  onBranch?: () => void;
  onFollowUp?: (q: string) => void;
  onRetry?: () => void;
  onFavoriteSection?: (s: SourceSection) => void;
  favoritedChunkIds?: Set<string>;
  sourcePanelFilters?: SourcePanelFilters;
  onSourcePanelFiltersChange?: (filters: SourcePanelFilters) => void;
}

export default function MessageBubble({
  role,
  content,
  sources,
  images,
  streaming,
  followUpQuestions,
  errorInfo,
  isAdmin,
  onSourceClick,
  onQuoteSource,
  onBranch,
  onFollowUp,
  onRetry,
  onFavoriteSection,
  favoritedChunkIds,
  sourcePanelFilters,
  onSourcePanelFiltersChange,
}: Props) {
  const [localFilters, setLocalFilters] = useState<SourcePanelFilters>(
    DEFAULT_SOURCE_PANEL_FILTERS,
  );
  const [tracePanelOpen, setTracePanelOpen] = useState(false);
  const effectiveFilters = sourcePanelFilters ?? localFilters;
  const activeSourceFilters = effectiveFilters.sourceTypes;
  const expandedOnly = effectiveFilters.expandedOnly;
  const activeTraceFilters = effectiveFilters.traceFilters;

  const updateFilters = (
    updater: (prev: SourcePanelFilters) => SourcePanelFilters,
  ) => {
    const next = updater(effectiveFilters);
    if (sourcePanelFilters && onSourcePanelFiltersChange) {
      onSourcePanelFiltersChange(next);
      return;
    }
    setLocalFilters(next);
  };

  const availableSourceFilters = useMemo(() => {
    const present = new Set<SourceFilterType>();
    for (const source of sources ?? []) {
      for (const type of source.source_type ?? []) {
        if (SOURCE_FILTER_ORDER.includes(type as SourceFilterType)) {
          present.add(type as SourceFilterType);
        }
      }
    }
    return SOURCE_FILTER_ORDER.filter((type) => present.has(type));
  }, [sources]);

  const availableTraceFilters = useMemo(() => {
    const present = new Set<string>();
    for (const source of sources ?? []) {
      for (const trace of source.retrieval_trace ?? []) {
        if (trace) present.add(trace);
      }
    }
    return Array.from(present).sort((a, b) => a.localeCompare(b));
  }, [sources]);

  const filteredSources = useMemo(() => {
    if (!sources?.length) return [];
    return sources.filter((source) => {
      const matchesSourceType =
        activeSourceFilters.length === 0 ||
        (source.source_type ?? []).some((type) =>
          activeSourceFilters.includes(type as SourceFilterType),
        );
      const matchesExpanded = !expandedOnly || Boolean(source.is_graph_expanded);
      const matchesTrace =
        activeTraceFilters.length === 0 ||
        (source.retrieval_trace ?? []).some((trace) =>
          activeTraceFilters.includes(trace),
        );
      return matchesSourceType && matchesExpanded && matchesTrace;
    });
  }, [activeSourceFilters, activeTraceFilters, expandedOnly, sources]);

  const sourceFilterCounts = useMemo(() => {
    const counts = new Map<SourceFilterType, number>();
    for (const type of SOURCE_FILTER_ORDER) {
      counts.set(type, 0);
    }
    for (const source of sources ?? []) {
      const hitTypes = new Set<SourceFilterType>();
      for (const type of source.source_type ?? []) {
        if (SOURCE_FILTER_ORDER.includes(type as SourceFilterType)) {
          hitTypes.add(type as SourceFilterType);
        }
      }
      for (const type of hitTypes) {
        counts.set(type, (counts.get(type) ?? 0) + 1);
      }
    }
    return counts;
  }, [sources]);

  const expandedCount = useMemo(
    () => (sources ?? []).filter((source) => source.is_graph_expanded).length,
    [sources],
  );

  const traceFilterCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const source of sources ?? []) {
      const uniqueTrace = new Set(source.retrieval_trace ?? []);
      for (const trace of uniqueTrace) {
        counts.set(trace, (counts.get(trace) ?? 0) + 1);
      }
    }
    return counts;
  }, [sources]);

  useEffect(() => {
    if (activeTraceFilters.length > 0) {
      setTracePanelOpen(true);
    }
  }, [activeTraceFilters.length]);

  const toggleSourceFilter = (filter: SourceFilterType) => {
    updateFilters((prev) => ({
      ...prev,
      sourceTypes: prev.sourceTypes.includes(filter)
        ? prev.sourceTypes.filter((item) => item !== filter)
        : [...prev.sourceTypes, filter],
    }));
  };

  const toggleTraceFilter = (trace: string) => {
    updateFilters((prev) => ({
      ...prev,
      traceFilters: prev.traceFilters.includes(trace)
        ? prev.traceFilters.filter((item) => item !== trace)
        : [...prev.traceFilters, trace],
    }));
  };

  const clearAllFilters = () => {
    updateFilters(() => ({
      sourceTypes: [],
      expandedOnly: false,
      traceFilters: [],
    }));
  };

  const toggleExpandedOnly = () => {
    updateFilters((prev) => ({
      ...prev,
      expandedOnly: !prev.expandedOnly,
    }));
  };

  if (role === "user") {
    return (
      <div className="flex justify-end mb-6">
        <div className="max-w-[75%] flex flex-col items-end gap-2">
          {images && images.length > 0 && (
            <div className="flex flex-wrap gap-2 justify-end">
              {images.map((src, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={`${src.slice(0, 32)}_${i}`}
                  src={src}
                  alt=""
                  className="max-h-48 max-w-xs rounded-xl border border-indigo-500/30 object-contain bg-gray-900"
                />
              ))}
            </div>
          )}
          {content && (
            <div className="px-4 py-3 bg-indigo-600 rounded-2xl rounded-tr-sm">
              <p className="text-sm text-white leading-relaxed whitespace-pre-wrap">
                {content}
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-[85%] w-full">
        {/* AI 头像 */}
        <div className="flex items-center gap-2 mb-2">
          <div
            className="w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/30
                          flex items-center justify-center text-xs text-indigo-400 font-bold"
          >
            AI
          </div>
          <span className="text-xs text-gray-600">CPS 知识库</span>
          {streaming && (
            <div className="flex items-center gap-1 ml-1">
              <div
                className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce"
                style={{ animationDelay: "0ms" }}
              />
              <div
                className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce"
                style={{ animationDelay: "150ms" }}
              />
              <div
                className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce"
                style={{ animationDelay: "300ms" }}
              />
            </div>
          )}
          {!streaming && onBranch && (
            <button
              type="button"
              onClick={onBranch}
              className="ml-2 text-xs text-gray-600 hover:text-indigo-400 transition-colors flex items-center gap-1"
              title="从此处开始新的分支对话"
            >
              <svg
                aria-hidden="true"
                className="w-3 h-3"
                viewBox="0 0 12 12"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <path d="M2 2v4a2 2 0 002 2h4M10 4l-2-2 2-2" />
              </svg>
              分支
            </button>
          )}
        </div>

        {/* 错误卡片 */}
        {errorInfo && (
          <div className="px-4 py-3 bg-amber-950/40 border border-amber-600/70 rounded-2xl rounded-tl-sm">
            <div className="flex items-start gap-2 mb-2">
              <AlertTriangle
                size={15}
                className="text-amber-400 mt-0.5 shrink-0"
              />
              <span className="text-sm font-medium text-amber-300">
                {errorInfo.code === "quota_exceeded" && "API 额度不足"}
                {errorInfo.code === "rate_limited" && "请求过于频繁"}
                {errorInfo.code === "timeout" && "模型响应超时"}
                {errorInfo.code === "service_unavailable" &&
                  "AI 服务暂时不可用"}
                {![
                  "quota_exceeded",
                  "rate_limited",
                  "timeout",
                  "service_unavailable",
                ].includes(errorInfo.code) && "AI 服务异常"}
              </span>
            </div>
            <p className="text-xs text-amber-200/80 mb-3">
              {errorInfo.message}
            </p>

            {isAdmin && (errorInfo.status_code || errorInfo.endpoint) && (
              <div className="mb-3 px-3 py-2 bg-amber-900/30 border border-amber-700/40 rounded-lg text-xs text-amber-300/70 space-y-1">
                <div className="font-medium text-amber-400 mb-1">
                  管理员信息
                </div>
                {errorInfo.status_code && (
                  <div>
                    HTTP 状态码：
                    <span className="font-mono">{errorInfo.status_code}</span>
                  </div>
                )}
                {errorInfo.endpoint && (
                  <div>
                    端点：
                    <span className="font-mono break-all">
                      {errorInfo.endpoint}
                    </span>
                  </div>
                )}
                {errorInfo.code === "quota_exceeded" && (
                  <div className="mt-1 space-y-0.5">
                    <div>建议操作：</div>
                    <div>· 充值：检查 API 提供商控制台</div>
                    <div>
                      · 或在 <span className="font-mono">.env</span> 设置{" "}
                      <span className="font-mono">LLM_MODE=local</span>{" "}
                      切换本地模型
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="text-xs text-amber-400/60 space-y-0.5">
              <div className="font-medium mb-1">你可以：</div>
              <div>
                {ERROR_HINTS[errorInfo.code] ?? ERROR_HINTS.unknown_error}
              </div>
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="mt-2 px-3 py-1 text-xs bg-amber-800/40 hover:bg-amber-700/50
                                               border border-amber-600/50 rounded-lg text-amber-300 transition-colors"
                >
                  重试
                </button>
              )}
            </div>
          </div>
        )}

        {/* 回答内容 */}
        {!errorInfo && (
          <div className="px-4 py-3 bg-gray-900 border border-gray-800 rounded-2xl rounded-tl-sm">
            <div
              className="text-sm text-gray-200 leading-relaxed prose prose-invert prose-sm max-w-none
                                    prose-headings:text-gray-100 prose-headings:font-semibold
                                    prose-p:text-gray-200 prose-p:leading-relaxed
                                    prose-strong:text-gray-100
                                    prose-code:text-indigo-300 prose-code:bg-gray-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
                                    prose-pre:bg-gray-800 prose-pre:border prose-pre:border-gray-700 prose-pre:rounded-lg
                                    prose-li:text-gray-200
                                    prose-a:text-indigo-400 prose-a:no-underline hover:prose-a:underline
                                    prose-blockquote:border-indigo-500 prose-blockquote:text-gray-400
                                    prose-hr:border-gray-700
                                    prose-table:text-gray-200 prose-th:text-gray-100 prose-td:border-gray-700 prose-th:border-gray-700"
            >
              {streaming ? (
                <>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {content}
                  </ReactMarkdown>
                  <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 animate-pulse align-middle" />
                </>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {content}
                </ReactMarkdown>
              )}
            </div>

            {/* 追问建议 */}
            {!streaming &&
              followUpQuestions &&
              followUpQuestions.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-800 animate-fade-in">
                  <div className="text-xs text-gray-600 mb-2">追问建议</div>
                  <div className="flex flex-col gap-1.5">
                    {followUpQuestions.map((q) => (
                      <button
                        key={q}
                        type="button"
                        onClick={() => onFollowUp?.(q)}
                        className="text-left px-3 py-1.5 text-xs text-indigo-300/80 bg-indigo-950/30
                                                   border border-indigo-800/40 rounded-lg hover:border-indigo-500/60
                                                   hover:text-indigo-200 hover:bg-indigo-950/50 transition-colors"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

            {/* 来源章节 */}
            {!streaming && sources && sources.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-800">
                <div className="mb-2 rounded-xl border border-gray-800/80 bg-gray-950/45 px-3 py-2">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                    <div className="text-xs font-medium text-gray-500">
                      引用来源
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      <button
                        type="button"
                        onClick={clearAllFilters}
                        className={`rounded-md border px-2 py-0.5 text-[11px] transition-colors ${
                          activeSourceFilters.length === 0 &&
                          !expandedOnly &&
                          activeTraceFilters.length === 0
                            ? "border-indigo-500 bg-indigo-500/15 text-indigo-200"
                            : "border-gray-700 bg-gray-800/80 text-gray-400 hover:border-gray-600 hover:text-gray-200"
                        }`}
                      >
                        全部
                        <span className="ml-1 text-[10px] text-inherit/80">
                          {sources.length}
                        </span>
                      </button>
                      {availableSourceFilters.map((type) => {
                        const active = activeSourceFilters.includes(type);
                        return (
                          <button
                            key={type}
                            type="button"
                            onClick={() => toggleSourceFilter(type)}
                            className={`rounded-md border px-2 py-0.5 text-[11px] transition-colors ${
                              active
                                ? type === "graph"
                                  ? "border-emerald-500 bg-emerald-500/15 text-emerald-200"
                                  : type === "vector"
                                    ? "border-sky-500 bg-sky-500/15 text-sky-200"
                                    : type === "fulltext"
                                      ? "border-amber-500 bg-amber-500/15 text-amber-200"
                                      : "border-violet-500 bg-violet-500/15 text-violet-200"
                                : "border-gray-700 bg-gray-800/80 text-gray-400 hover:border-gray-600 hover:text-gray-200"
                            }`}
                          >
                            {SOURCE_LABELS[type]}
                            <span className="ml-1 text-[10px] text-inherit/80">
                              {sourceFilterCounts.get(type) ?? 0}
                            </span>
                          </button>
                        );
                      })}
                      {expandedCount > 0 && (
                        <button
                          type="button"
                          onClick={toggleExpandedOnly}
                          className={`rounded-md border px-2 py-0.5 text-[11px] transition-colors ${
                            expandedOnly
                              ? "border-emerald-500 bg-emerald-500/15 text-emerald-200"
                              : "border-gray-700 bg-gray-800/80 text-gray-400 hover:border-gray-600 hover:text-gray-200"
                          }`}
                        >
                          扩展命中
                          <span className="ml-1 text-[10px] text-inherit/80">
                            {expandedCount}
                          </span>
                        </button>
                      )}
                    </div>
                  </div>

                  {availableTraceFilters.length > 0 && (
                    <div className="mt-2 rounded-lg border border-gray-800/70 bg-gray-950/40">
                      <button
                        type="button"
                        onClick={() => setTracePanelOpen((prev) => !prev)}
                        className="flex w-full items-center justify-between gap-3 px-2.5 py-2 text-left"
                      >
                        <div className="flex min-w-0 items-center gap-2">
                          <svg
                            aria-hidden="true"
                            className={`h-3 w-3 flex-shrink-0 text-gray-500 transition-transform ${tracePanelOpen ? "rotate-90" : ""}`}
                            viewBox="0 0 12 12"
                            fill="currentColor"
                          >
                            <path d="M4 2l5 4-5 4V2z" />
                          </svg>
                          <span className="text-[11px] font-medium text-gray-400">
                            Trace 细分
                          </span>
                          <span className="rounded bg-gray-900 px-1.5 py-0.5 text-[10px] text-gray-500">
                            {availableTraceFilters.length}
                          </span>
                          {activeTraceFilters.length > 0 && (
                            <span className="rounded bg-indigo-500/10 px-1.5 py-0.5 text-[10px] text-indigo-300">
                              已选 {activeTraceFilters.length}
                            </span>
                          )}
                        </div>
                        <span className="truncate text-[10px] text-gray-600">
                          {tracePanelOpen
                            ? "收起"
                            : activeTraceFilters.length > 0
                              ? activeTraceFilters.join(" / ")
                              : "按 retrieval_trace 细分"}
                        </span>
                      </button>

                      {tracePanelOpen && (
                        <div className="grid grid-cols-1 gap-1 border-t border-gray-800/70 px-2.5 py-2 lg:grid-cols-2">
                          {availableTraceFilters.map((trace) => {
                            const active = activeTraceFilters.includes(trace);
                            return (
                              <button
                                key={trace}
                                type="button"
                                onClick={() => toggleTraceFilter(trace)}
                                className={`flex w-full items-center justify-between gap-2 rounded-md border px-2 py-1 text-left text-[10px] font-mono leading-4 transition-colors ${
                                  active
                                    ? "border-indigo-500 bg-indigo-500/10 text-indigo-200"
                                    : "border-gray-800 bg-gray-950/80 text-gray-500 hover:border-gray-700 hover:text-gray-300"
                                }`}
                                title={trace}
                              >
                                <span className="min-w-0 flex-1 truncate">
                                  {trace}
                                </span>
                                <span className="flex-shrink-0 text-[10px] text-inherit/80">
                                  {traceFilterCounts.get(trace) ?? 0}
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                {(activeSourceFilters.length > 0 ||
                  expandedOnly ||
                  activeTraceFilters.length > 0) && (
                  <div className="mb-2 text-[11px] text-gray-500">
                    当前仅显示：
                    {[
                      ...activeSourceFilters.map(
                        (type) => SOURCE_LABELS[type] ?? type,
                      ),
                      ...(expandedOnly ? ["扩展命中"] : []),
                      ...activeTraceFilters,
                    ].join(" / ")}
                    ，共 {filteredSources.length} 条
                  </div>
                )}
                {filteredSources.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-gray-800 bg-gray-950/60 px-3 py-3 text-xs text-gray-500">
                    当前筛选下没有匹配的来源，切换到“全部”或其他来源标签试试看。
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-1.5 lg:grid-cols-2">
                    {filteredSources.map((s, idx) => (
                      <div
                        key={s.chunk_id}
                        className="h-full rounded-xl border border-gray-800 bg-gray-950/55 px-2.5 py-2"
                      >
                        <div className="flex items-start gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              onSourceClick?.(s.chunk_id);
                              onQuoteSource?.(s);
                            }}
                            title="点击追问此章节"
                            className="group flex min-w-0 flex-1 items-start gap-2 rounded-lg border border-gray-700 bg-gray-800/70 px-2 py-1.5 text-left transition-colors hover:border-indigo-500 hover:bg-indigo-900/20"
                          >
                            <span
                              className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-gray-900"
                              style={{
                                backgroundColor: RANK_COLORS[idx] ?? "#6b7280",
                              }}
                            >
                              {idx + 1}
                            </span>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-1.5">
                                <span className="text-xs font-mono text-indigo-400">
                                  {s.doc_id} §{s.number}
                                </span>
                                {s.page_idx !== undefined && (
                                  <span className="rounded bg-gray-900 px-1 py-0.5 text-[10px] text-gray-500">
                                    P{s.page_idx + 1}
                                  </span>
                                )}
                              </div>
                              <div className="mt-0.5 truncate text-xs text-gray-300">
                                {s.title}
                              </div>
                            </div>
                            <Reply
                              size={10}
                              className="mt-0.5 flex-shrink-0 text-gray-600 transition-colors group-hover:text-indigo-400"
                            />
                          </button>
                          <div className="flex flex-shrink-0 items-center gap-1">
                            <Link
                              href={`/library/${s.doc_id}${s.page_idx !== undefined ? `?page=${s.page_idx}` : ""}`}
                              title="查看原文并跳转锚点"
                              className="rounded-lg border border-gray-700 p-1.5 text-gray-500 transition-colors hover:border-indigo-500 hover:text-indigo-400"
                            >
                              <ExternalLink size={10} />
                            </Link>
                            {onFavoriteSection && (
                              <button
                                type="button"
                                onClick={() => onFavoriteSection(s)}
                                title={
                                  favoritedChunkIds?.has(s.chunk_id)
                                    ? "取消收藏"
                                    : "收藏此章节"
                                }
                                className="rounded-lg border border-gray-700 p-1.5 transition-colors hover:border-amber-500"
                              >
                                <Star
                                  size={10}
                                  className={
                                    favoritedChunkIds?.has(s.chunk_id)
                                      ? "text-amber-400 fill-amber-400"
                                      : "text-gray-600 hover:text-amber-400"
                                  }
                                />
                              </button>
                            )}
                          </div>
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                          {(s.source_type ?? []).map((type) => (
                            <span
                              key={`${s.chunk_id}_${type}`}
                              className={`rounded-md border px-1.5 py-0.5 text-[10px] leading-4 ${
                                type === "graph"
                                  ? "border-emerald-700 bg-emerald-950/50 text-emerald-300"
                                  : type === "vector"
                                    ? "border-sky-700 bg-sky-950/50 text-sky-300"
                                    : type === "fulltext"
                                      ? "border-amber-700 bg-amber-950/50 text-amber-300"
                                      : "border-violet-700 bg-violet-950/50 text-violet-300"
                              }`}
                            >
                              {SOURCE_LABELS[type] ?? type}
                            </span>
                          ))}
                          {s.is_graph_expanded && (
                            <span className="rounded-md border border-emerald-800/80 bg-emerald-950/30 px-1.5 py-0.5 text-[10px] leading-4 text-emerald-200/80">
                              扩展命中
                            </span>
                          )}
                          {s.retrieval_trace && s.retrieval_trace.length > 0 && (
                            <button
                              type="button"
                              onClick={() =>
                                toggleTraceFilter(s.retrieval_trace?.[0] ?? "")
                              }
                              className="max-w-full rounded-md border border-gray-800 bg-gray-900/80 px-1.5 py-0.5 font-mono text-[10px] leading-4 text-gray-500 transition-colors hover:border-gray-700 hover:text-gray-300"
                              title={s.retrieval_trace.join(" -> ")}
                            >
                              <span className="mr-1 text-gray-600">trace</span>
                              <span className="truncate">
                                {s.retrieval_trace[0]}
                                {s.retrieval_trace.length > 1 &&
                                  ` +${s.retrieval_trace.length - 1}`}
                              </span>
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {/* 来源图谱 */}
                <SourceGraph sources={filteredSources} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
