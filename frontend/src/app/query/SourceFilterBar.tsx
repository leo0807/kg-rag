"use client";

import { useState } from "react";
import type { SourceFilterType, SourceSection } from "./types";

const SOURCE_LABELS: Record<string, string> = {
  fulltext: "全文", vector: "向量", graph: "图谱扩展", gnn: "GNN",
};

interface Props {
  sources: SourceSection[];
  activeSourceFilters: SourceFilterType[];
  expandedOnly: boolean;
  activeTraceFilters: string[];
  availableSourceFilters: SourceFilterType[];
  availableTraceFilters: string[];
  sourceFilterCounts: Map<SourceFilterType, number>;
  expandedCount: number;
  traceFilterCounts: Map<string, number>;
  filteredCount: number;
  onToggleSourceFilter: (type: SourceFilterType) => void;
  onToggleExpandedOnly: () => void;
  onToggleTraceFilter: (trace: string) => void;
  onClearAll: () => void;
}

export function SourceFilterBar({
  sources, activeSourceFilters, expandedOnly, activeTraceFilters,
  availableSourceFilters, availableTraceFilters, sourceFilterCounts,
  expandedCount, traceFilterCounts, filteredCount,
  onToggleSourceFilter, onToggleExpandedOnly, onToggleTraceFilter, onClearAll,
}: Props) {
  const [tracePanelOpen, setTracePanelOpen] = useState(false);
  const hasFilter = activeSourceFilters.length > 0 || expandedOnly || activeTraceFilters.length > 0;

  return (
    <div className="mb-2 rounded-xl border border-gray-800/80 bg-gray-950/45 px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <div className="text-xs font-medium text-gray-500">引用来源</div>
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={onClearAll}
            className={`rounded-md border px-2 py-0.5 text-[11px] transition-colors ${
              !hasFilter
                ? "border-indigo-500 bg-indigo-500/15 text-indigo-200"
                : "border-gray-700 bg-gray-800/80 text-gray-400 hover:border-gray-600 hover:text-gray-200"
            }`}
          >
            全部<span className="ml-1 text-[10px] text-inherit/80">{sources.length}</span>
          </button>

          {availableSourceFilters.map((type) => {
            const active = activeSourceFilters.includes(type);
            const colorMap: Record<string, string> = {
              graph: "border-emerald-500 bg-emerald-500/15 text-emerald-200",
              vector: "border-sky-500 bg-sky-500/15 text-sky-200",
              fulltext: "border-amber-500 bg-amber-500/15 text-amber-200",
            };
            return (
              <button
                key={type}
                type="button"
                onClick={() => onToggleSourceFilter(type)}
                className={`rounded-md border px-2 py-0.5 text-[11px] transition-colors ${
                  active
                    ? (colorMap[type] ?? "border-violet-500 bg-violet-500/15 text-violet-200")
                    : "border-gray-700 bg-gray-800/80 text-gray-400 hover:border-gray-600 hover:text-gray-200"
                }`}
              >
                {SOURCE_LABELS[type]}<span className="ml-1 text-[10px] text-inherit/80">{sourceFilterCounts.get(type) ?? 0}</span>
              </button>
            );
          })}

          {expandedCount > 0 && (
            <button
              type="button"
              onClick={onToggleExpandedOnly}
              className={`rounded-md border px-2 py-0.5 text-[11px] transition-colors ${
                expandedOnly
                  ? "border-emerald-500 bg-emerald-500/15 text-emerald-200"
                  : "border-gray-700 bg-gray-800/80 text-gray-400 hover:border-gray-600 hover:text-gray-200"
              }`}
            >
              扩展命中<span className="ml-1 text-[10px] text-inherit/80">{expandedCount}</span>
            </button>
          )}
        </div>
      </div>

      {availableTraceFilters.length > 0 && (
        <div className="mt-2 rounded-lg border border-gray-800/70 bg-gray-950/40">
          <button
            type="button"
            onClick={() => setTracePanelOpen(prev => !prev)}
            className="flex w-full items-center justify-between gap-3 px-2.5 py-2 text-left"
          >
            <div className="flex min-w-0 items-center gap-2">
              <svg aria-hidden="true"
                className={`h-3 w-3 flex-shrink-0 text-gray-500 transition-transform ${tracePanelOpen ? "rotate-90" : ""}`}
                viewBox="0 0 12 12" fill="currentColor">
                <path d="M4 2l5 4-5 4V2z" />
              </svg>
              <span className="text-[11px] font-medium text-gray-400">Trace 细分</span>
              <span className="rounded bg-gray-900 px-1.5 py-0.5 text-[10px] text-gray-500">{availableTraceFilters.length}</span>
              {activeTraceFilters.length > 0 && (
                <span className="rounded bg-indigo-500/10 px-1.5 py-0.5 text-[10px] text-indigo-300">已选 {activeTraceFilters.length}</span>
              )}
            </div>
            <span className="truncate text-[10px] text-gray-600">
              {tracePanelOpen ? "收起" : activeTraceFilters.length > 0 ? activeTraceFilters.join(" / ") : "按 retrieval_trace 细分"}
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
                    onClick={() => onToggleTraceFilter(trace)}
                    className={`flex w-full items-center justify-between gap-2 rounded-md border px-2 py-1 text-left text-[10px] font-mono leading-4 transition-colors ${
                      active
                        ? "border-indigo-500 bg-indigo-500/10 text-indigo-200"
                        : "border-gray-800 bg-gray-950/80 text-gray-500 hover:border-gray-700 hover:text-gray-300"
                    }`}
                    title={trace}
                  >
                    <span className="min-w-0 flex-1 truncate">{trace}</span>
                    <span className="flex-shrink-0 text-[10px] text-inherit/80">{traceFilterCounts.get(trace) ?? 0}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {hasFilter && (
        <div className="mt-1.5 text-[11px] text-gray-500">
          当前仅显示：
          {[
            ...activeSourceFilters.map(t => SOURCE_LABELS[t] ?? t),
            ...(expandedOnly ? ["扩展命中"] : []),
            ...activeTraceFilters,
          ].join(" / ")}
          ，共 {filteredCount} 条
        </div>
      )}
    </div>
  );
}
