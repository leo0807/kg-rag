"use client";

import { useMemo, useState } from "react";
import { KnowledgeCapturePanel } from "./KnowledgeCapturePanel";
import { MetricsPanel } from "./MetricsPanel";
import { SourceCard } from "./SourceCard";
import { SourceFilterBar } from "./SourceFilterBar";
import SourceGraph from "./SourceGraph";
import type { QueryMetrics, SourceSection } from "./types";
import type { SourcePanelState } from "./useSourcePanelState";

const SOURCE_COLLAPSE_THRESHOLD = 6;

interface Props {
  content: string;
  metrics?: QueryMetrics;
  onSourceClick?: (chunkId: string) => void;
  onQuoteSource?: (source: SourceSection) => void;
  onFavoriteSection?: (s: SourceSection) => void;
  favoritedChunkIds?: Set<string>;
  state: SourcePanelState;
}

export function AssistantMessageExtras({
  content,
  metrics,
  onSourceClick,
  onQuoteSource,
  onFavoriteSection,
  favoritedChunkIds,
  state,
}: Props) {
  const {
    filteredSources,
    activeSourceFilters,
    expandedOnly,
    activeTraceFilters,
    availableSourceFilters,
    availableTraceFilters,
    sourceFilterCounts,
    expandedCount,
    traceFilterCounts,
    toggleSourceFilter,
    toggleExpandedOnly,
    toggleTraceFilter,
    clearAllFilters,
  } = state;
  const [sourcesExpanded, setSourcesExpanded] = useState(false);
  const showCollapseToggle = filteredSources.length > SOURCE_COLLAPSE_THRESHOLD;
  const visibleSources = useMemo(
    () =>
      showCollapseToggle && !sourcesExpanded
        ? filteredSources.slice(0, SOURCE_COLLAPSE_THRESHOLD)
        : filteredSources,
    [filteredSources, showCollapseToggle, sourcesExpanded],
  );

  return (
    <>
      <div className="mt-3 border-t border-gray-800 pt-3">
        <SourceFilterBar
          sources={filteredSources}
          activeSourceFilters={activeSourceFilters}
          expandedOnly={expandedOnly}
          activeTraceFilters={activeTraceFilters}
          availableSourceFilters={availableSourceFilters}
          availableTraceFilters={availableTraceFilters}
          sourceFilterCounts={sourceFilterCounts}
          expandedCount={expandedCount}
          traceFilterCounts={traceFilterCounts}
          filteredCount={filteredSources.length}
          onToggleSourceFilter={toggleSourceFilter}
          onToggleExpandedOnly={toggleExpandedOnly}
          onToggleTraceFilter={toggleTraceFilter}
          onClearAll={clearAllFilters}
        />
        {filteredSources.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-800 bg-gray-950/60 px-3 py-3 text-xs text-gray-500">
            当前筛选下没有匹配的来源，切换到"全部"或其他来源标签试试看。
          </div>
        ) : (
          <>
            {showCollapseToggle && (
              <div className="mb-2 flex items-center justify-between rounded-lg border border-gray-800/70 bg-gray-950/50 px-3 py-2 text-[11px] text-gray-500">
                <span>
                  已显示 {visibleSources.length} / {filteredSources.length}{" "}
                  条来源
                </span>
                <button
                  type="button"
                  onClick={() => setSourcesExpanded((v) => !v)}
                  className="rounded-md border border-gray-700 px-2 py-1 text-[11px] text-gray-300 transition-colors hover:border-indigo-500 hover:text-indigo-300"
                >
                  {sourcesExpanded
                    ? "收起来源"
                    : `展开全部来源（共 ${filteredSources.length} 条）`}
                </button>
              </div>
            )}
            <div className="grid grid-cols-1 gap-1.5 lg:grid-cols-2">
              {visibleSources.map((s, idx) => (
                <SourceCard
                  key={s.chunk_id}
                  source={s}
                  index={idx}
                  onSourceClick={onSourceClick}
                  onQuoteSource={onQuoteSource}
                  onFavoriteSection={onFavoriteSection}
                  favoritedChunkIds={favoritedChunkIds}
                  onToggleTrace={toggleTraceFilter}
                />
              ))}
            </div>
          </>
        )}
        <SourceGraph sources={visibleSources} />
      </div>
      <MetricsPanel metrics={metrics} />
      {content && <KnowledgeCapturePanel answerText={content} />}
    </>
  );
}
