"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import SourceGraph from "./SourceGraph";
import { MessageError } from "./MessageError";
import { FollowUpSuggestions } from "./FollowUpSuggestions";
import { SourceCard } from "./SourceCard";
import { SourceFilterBar } from "./SourceFilterBar";
import DetailedFeedbackPanel from "./DetailedFeedbackPanel";
import { KnowledgeCapturePanel } from "./KnowledgeCapturePanel";
import type { LLMErrorInfo, QueryMetrics, SourceFilterType, SourcePanelFilters, SourceSection } from "./types";
import { MetricsPanel } from "./MetricsPanel";

const SOURCE_FILTER_ORDER = ["fulltext", "vector", "graph", "gnn"] as const;
const DEFAULT_SOURCE_PANEL_FILTERS: SourcePanelFilters = { sourceTypes: [], expandedOnly: false, traceFilters: [] };

interface Props {
  role: "user" | "assistant";
  content: string;
  sources?: SourceSection[];
  images?: string[];
  streaming?: boolean;
  followUpQuestions?: string[];
  errorInfo?: LLMErrorInfo;
  expansionInfo?: string[];
  metrics?: QueryMetrics;
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
  question?: string;
  strategy?: string;
  onLowScoreRetry?: (q: string) => void;
}

export default function MessageBubble({
  role, content, sources, images, streaming, followUpQuestions, errorInfo, expansionInfo, metrics, isAdmin,
  onSourceClick, onQuoteSource, onBranch, onFollowUp, onRetry, onFavoriteSection,
  favoritedChunkIds, sourcePanelFilters, onSourcePanelFiltersChange,
  question, strategy, onLowScoreRetry,
}: Props) {
  const [localFilters, setLocalFilters] = useState<SourcePanelFilters>(DEFAULT_SOURCE_PANEL_FILTERS);
  const [feedback, setFeedback] = useState<{ rating: number; id: number | null; showDetail: boolean } | null>(null);

  async function rate(r: number) {
    if (!question) return;
    const t = localStorage.getItem("token") ?? "";
    const res = await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` }, body: JSON.stringify({ question, answer: content, sources: sources ?? [], rating: r, strategy: strategy ?? "parallel" }) });
    if (res.ok) { const d = await res.json(); setFeedback({ rating: r, id: d.id ?? null, showDetail: true }); }
  }
  const effectiveFilters = sourcePanelFilters ?? localFilters;
  const { sourceTypes: activeSourceFilters, expandedOnly, traceFilters: activeTraceFilters } = effectiveFilters;

  function updateFilters(updater: (prev: SourcePanelFilters) => SourcePanelFilters) {
    const next = updater(effectiveFilters);
    if (sourcePanelFilters && onSourcePanelFiltersChange) { onSourcePanelFiltersChange(next); return; }
    setLocalFilters(next);
  }

  const availableSourceFilters = useMemo(() => {
    const present = new Set<SourceFilterType>();
    for (const source of sources ?? []) {
      for (const type of source.source_type ?? []) {
        if (SOURCE_FILTER_ORDER.includes(type as SourceFilterType)) present.add(type as SourceFilterType);
      }
    }
    return SOURCE_FILTER_ORDER.filter(type => present.has(type));
  }, [sources]);

  const availableTraceFilters = useMemo(() => {
    const present = new Set<string>();
    for (const source of sources ?? []) {
      for (const trace of source.retrieval_trace ?? []) { if (trace) present.add(trace); }
    }
    return Array.from(present).sort((a, b) => a.localeCompare(b));
  }, [sources]);

  const filteredSources = useMemo(() => {
    if (!sources?.length) return [];
    return sources.filter(source => {
      const matchesSourceType = activeSourceFilters.length === 0 || (source.source_type ?? []).some(t => activeSourceFilters.includes(t as SourceFilterType));
      const matchesExpanded = !expandedOnly || Boolean(source.is_graph_expanded);
      const matchesTrace = activeTraceFilters.length === 0 || (source.retrieval_trace ?? []).some(t => activeTraceFilters.includes(t));
      return matchesSourceType && matchesExpanded && matchesTrace;
    });
  }, [activeSourceFilters, activeTraceFilters, expandedOnly, sources]);

  const sourceFilterCounts = useMemo(() => {
    const counts = new Map<SourceFilterType, number>(SOURCE_FILTER_ORDER.map(t => [t, 0]));
    for (const source of sources ?? []) {
      const hitTypes = new Set<SourceFilterType>((source.source_type ?? []).filter(t => SOURCE_FILTER_ORDER.includes(t as SourceFilterType)) as SourceFilterType[]);
      for (const type of hitTypes) counts.set(type, (counts.get(type) ?? 0) + 1);
    }
    return counts;
  }, [sources]);

  const expandedCount = useMemo(() => (sources ?? []).filter(s => s.is_graph_expanded).length, [sources]);

  const traceFilterCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const source of sources ?? []) {
      for (const trace of new Set(source.retrieval_trace ?? [])) counts.set(trace, (counts.get(trace) ?? 0) + 1);
    }
    return counts;
  }, [sources]);

  const toggleSourceFilter = (filter: SourceFilterType) =>
    updateFilters(prev => ({ ...prev, sourceTypes: prev.sourceTypes.includes(filter) ? prev.sourceTypes.filter(i => i !== filter) : [...prev.sourceTypes, filter] }));
  const toggleTraceFilter = (trace: string) =>
    updateFilters(prev => ({ ...prev, traceFilters: prev.traceFilters.includes(trace) ? prev.traceFilters.filter(i => i !== trace) : [...prev.traceFilters, trace] }));
  const clearAllFilters = () => updateFilters(() => DEFAULT_SOURCE_PANEL_FILTERS);
  const toggleExpandedOnly = () => updateFilters(prev => ({ ...prev, expandedOnly: !prev.expandedOnly }));

  if (role === "user") {
    return (
      <div className="flex justify-end mb-6">
        <div className="max-w-[75%] flex flex-col items-end gap-2">
          {images && images.length > 0 && (
            <div className="flex flex-wrap gap-2 justify-end">
              {images.map((src, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img key={`${src.slice(0, 32)}_${i}`} src={src} alt=""
                  className="max-h-48 max-w-xs rounded-xl border border-indigo-500/30 object-contain bg-gray-900" />
              ))}
            </div>
          )}
          {content && (
            <div className="px-4 py-3 bg-[#1B6BB5] rounded-2xl rounded-tr-sm">
              <p className="text-sm text-white leading-relaxed whitespace-pre-wrap">{content}</p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-6">
      <div className="max-w-[85%] w-full">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-6 h-6 rounded-full bg-[#1B6BB5]/20 border border-[#1B6BB5]/30 flex items-center justify-center text-xs text-[#1B6BB5] dark:text-[#5BA3E0] font-bold">AI</div>
          <span className="text-xs text-gray-600">CPS 知识库</span>
          {streaming && (
            <div className="flex items-center gap-1 ml-1">
              {[0, 150, 300].map(delay => (
                <div key={delay} className="w-1 h-1 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: `${delay}ms` }} />
              ))}
            </div>
          )}
          {!streaming && onBranch && (
            <button type="button" onClick={onBranch}
              className="ml-2 text-xs text-gray-600 hover:text-indigo-400 transition-colors flex items-center gap-1"
              title="从此处开始新的分支对话">
              <svg aria-hidden="true" className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M2 2v4a2 2 0 002 2h4M10 4l-2-2 2-2" />
              </svg>
              分支
            </button>
          )}
        </div>

        {errorInfo && <MessageError errorInfo={errorInfo} isAdmin={isAdmin} onRetry={onRetry} />}

        {!errorInfo && (
          <div className="px-4 py-3 bg-gray-900 border border-gray-800 rounded-2xl rounded-tl-sm">
            <div className="text-sm text-gray-200 leading-relaxed prose prose-invert prose-sm max-w-none
              prose-headings:text-gray-100 prose-headings:font-semibold prose-p:text-gray-200 prose-p:leading-relaxed
              prose-strong:text-gray-100 prose-code:text-indigo-300 prose-code:bg-gray-800 prose-code:px-1 prose-code:py-0.5
              prose-code:rounded prose-code:text-xs prose-pre:bg-gray-800 prose-pre:border prose-pre:border-gray-700
              prose-pre:rounded-lg prose-li:text-gray-200 prose-a:text-indigo-400 prose-a:no-underline hover:prose-a:underline
              prose-blockquote:border-indigo-500 prose-blockquote:text-gray-400 prose-hr:border-gray-700
              prose-table:text-gray-200 prose-th:text-gray-100 prose-td:border-gray-700 prose-th:border-gray-700">
              {streaming ? (
                <><ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                  <span className="inline-block w-0.5 h-4 bg-indigo-400 ml-0.5 animate-pulse align-middle" /></>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
              )}
            </div>

            {!streaming && expansionInfo && expansionInfo.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {expansionInfo.map((info) => (
                  <span key={info} className="inline-flex items-center gap-1 rounded-md border border-violet-800/50 bg-violet-950/40 px-1.5 py-0.5 text-[10px] text-violet-300">
                    <span className="text-violet-500">扩展</span>{info}
                  </span>
                ))}
              </div>
            )}

            {!streaming && followUpQuestions && followUpQuestions.length > 0 && (
              <FollowUpSuggestions questions={followUpQuestions} onFollowUp={onFollowUp} />
            )}

            {!streaming && sources && sources.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-800">
                <SourceFilterBar
                  sources={sources} activeSourceFilters={activeSourceFilters} expandedOnly={expandedOnly}
                  activeTraceFilters={activeTraceFilters} availableSourceFilters={availableSourceFilters}
                  availableTraceFilters={availableTraceFilters} sourceFilterCounts={sourceFilterCounts}
                  expandedCount={expandedCount} traceFilterCounts={traceFilterCounts} filteredCount={filteredSources.length}
                  onToggleSourceFilter={toggleSourceFilter} onToggleExpandedOnly={toggleExpandedOnly}
                  onToggleTraceFilter={toggleTraceFilter} onClearAll={clearAllFilters}
                />
                {filteredSources.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-gray-800 bg-gray-950/60 px-3 py-3 text-xs text-gray-500">
                    当前筛选下没有匹配的来源，切换到"全部"或其他来源标签试试看。
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-1.5 lg:grid-cols-2">
                    {filteredSources.map((s, idx) => (
                      <SourceCard key={s.chunk_id} source={s} index={idx}
                        onSourceClick={onSourceClick} onQuoteSource={onQuoteSource}
                        onFavoriteSection={onFavoriteSection} favoritedChunkIds={favoritedChunkIds}
                        onToggleTrace={toggleTraceFilter}
                      />
                    ))}
                  </div>
                )}
                <SourceGraph sources={filteredSources} />
              </div>
            )}

            {!streaming && <MetricsPanel metrics={metrics} />}
            {!streaming && content && <KnowledgeCapturePanel answerText={content} />}
            {!streaming && question && (
              <div className="mt-3 pt-2 border-t border-gray-800">
                {!feedback ? (
                  <div className="flex items-center gap-2">
                    <button onClick={() => rate(1)} className="text-lg hover:scale-110 transition-transform">👍</button>
                    <button onClick={() => rate(-1)} className="text-lg hover:scale-110 transition-transform">👎</button>
                    <span className="text-xs text-gray-700">对这个回答有帮助吗？</span>
                  </div>
                ) : <span className="text-xs text-gray-600">{feedback.rating === 1 ? "👍" : "👎"} 感谢反馈</span>}
                {feedback?.showDetail && feedback.id !== null && (
                  <DetailedFeedbackPanel feedbackId={feedback.id}
                    onDone={avg => { setFeedback(s => s ? {...s, showDetail: false} : null); if (avg < 2 && onLowScoreRetry) onLowScoreRetry(question); }}
                    onSkip={() => setFeedback(s => s ? {...s, showDetail: false} : null)} />
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
