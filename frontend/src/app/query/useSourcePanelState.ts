"use client";

import { useMemo, useState } from "react";
import type {
  SourceFilterType,
  SourcePanelFilters,
  SourceSection,
} from "./types";

const SOURCE_FILTER_ORDER = ["fulltext", "vector", "graph", "gnn"] as const;
const DEFAULT_SOURCE_PANEL_FILTERS: SourcePanelFilters = {
  sourceTypes: [],
  expandedOnly: false,
  traceFilters: [],
};

export function useSourcePanelState(sources?: SourceSection[]) {
  const [localFilters, setLocalFilters] = useState<SourcePanelFilters>(
    DEFAULT_SOURCE_PANEL_FILTERS,
  );

  const availableSourceFilters = useMemo(() => {
    const present = new Set<SourceFilterType>();
    for (const source of sources ?? []) {
      for (const type of source.source_type ?? []) {
        if (SOURCE_FILTER_ORDER.includes(type as SourceFilterType))
          present.add(type as SourceFilterType);
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

  const effectiveFilters = localFilters;
  const {
    sourceTypes: activeSourceFilters,
    expandedOnly,
    traceFilters: activeTraceFilters,
  } = effectiveFilters;

  const filteredSources = useMemo(() => {
    if (!sources?.length) return [];
    return sources.filter((source) => {
      const matchesSourceType =
        activeSourceFilters.length === 0 ||
        (source.source_type ?? []).some((t) =>
          activeSourceFilters.includes(t as SourceFilterType),
        );
      const matchesExpanded =
        !expandedOnly || Boolean(source.is_graph_expanded);
      const matchesTrace =
        activeTraceFilters.length === 0 ||
        (source.retrieval_trace ?? []).some((t) =>
          activeTraceFilters.includes(t),
        );
      return matchesSourceType && matchesExpanded && matchesTrace;
    });
  }, [activeSourceFilters, activeTraceFilters, expandedOnly, sources]);

  const sourceFilterCounts = useMemo(() => {
    const counts = new Map<SourceFilterType, number>(
      SOURCE_FILTER_ORDER.map((t) => [t, 0]),
    );
    for (const source of sources ?? []) {
      const hitTypes = new Set<SourceFilterType>(
        (source.source_type ?? []).filter((t) =>
          SOURCE_FILTER_ORDER.includes(t as SourceFilterType),
        ) as SourceFilterType[],
      );
      for (const type of hitTypes)
        counts.set(type, (counts.get(type) ?? 0) + 1);
    }
    return counts;
  }, [sources]);

  const expandedCount = useMemo(
    () => (sources ?? []).filter((s) => s.is_graph_expanded).length,
    [sources],
  );

  const traceFilterCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const source of sources ?? []) {
      for (const trace of new Set(source.retrieval_trace ?? []))
        counts.set(trace, (counts.get(trace) ?? 0) + 1);
    }
    return counts;
  }, [sources]);

  function updateFilters(
    updater: (prev: SourcePanelFilters) => SourcePanelFilters,
  ) {
    setLocalFilters(updater(effectiveFilters));
  }

  const toggleSourceFilter = (filter: SourceFilterType) =>
    updateFilters((prev) => ({
      ...prev,
      sourceTypes: prev.sourceTypes.includes(filter)
        ? prev.sourceTypes.filter((i) => i !== filter)
        : [...prev.sourceTypes, filter],
    }));
  const toggleTraceFilter = (trace: string) =>
    updateFilters((prev) => ({
      ...prev,
      traceFilters: prev.traceFilters.includes(trace)
        ? prev.traceFilters.filter((i) => i !== trace)
        : [...prev.traceFilters, trace],
    }));
  const clearAllFilters = () =>
    updateFilters(() => DEFAULT_SOURCE_PANEL_FILTERS);
  const toggleExpandedOnly = () =>
    updateFilters((prev) => ({ ...prev, expandedOnly: !prev.expandedOnly }));

  return {
    availableSourceFilters,
    availableTraceFilters,
    activeSourceFilters,
    activeTraceFilters,
    expandedOnly,
    filteredSources,
    sourceFilterCounts,
    expandedCount,
    traceFilterCounts,
    toggleSourceFilter,
    toggleTraceFilter,
    clearAllFilters,
    toggleExpandedOnly,
  };
}

export type SourcePanelState = ReturnType<typeof useSourcePanelState>;
