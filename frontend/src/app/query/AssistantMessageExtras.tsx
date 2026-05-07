"use client";

import { KnowledgeCapturePanel } from "./KnowledgeCapturePanel";
import { MetricsPanel } from "./MetricsPanel";
import { SourceCard } from "./SourceCard";
import { SourceFilterBar } from "./SourceFilterBar";
import SourceGraph from "./SourceGraph";
import type { QueryMetrics, SourceSection } from "./types";
import type { SourcePanelState } from "./useSourcePanelState";

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
          <div className="grid grid-cols-1 gap-1.5 lg:grid-cols-2">
            {filteredSources.map((s, idx) => (
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
        )}
        <SourceGraph sources={filteredSources} />
      </div>
      <MetricsPanel metrics={metrics} />
      {content && <KnowledgeCapturePanel answerText={content} />}
    </>
  );
}
