"use client";

import type {
  EdgeFilter,
  GraphNode,
  GraphStats,
  NodeFilter,
  RenderMode,
} from "./constants";
import { GraphFilterPanel } from "./GraphFilterPanel";
import { GraphLevelControl } from "./GraphLevelControl";
import { GraphToolbarActions } from "./GraphToolbarActions";
import {
  GraphToolbarSearch,
  type SearchDocumentResult,
} from "./GraphToolbarSearch";

interface Props {
  nodeFilter: NodeFilter;
  setNodeFilter: (v: NodeFilter) => void;
  edgeFilter: EdgeFilter;
  setEdgeFilter: (v: EdgeFilter) => void;
  searchQuery: string;
  handleSearch: (q: string) => void;
  searchNodeResults: GraphNode[];
  searchDocResults: SearchDocumentResult[];
  onSelectNodeResult: (node: GraphNode) => void;
  onSelectDocumentResult: (doc: SearchDocumentResult) => void;
  docFilter: string;
  setDocFilter: (v: string) => void;
  docs: { doc_id: string; title: string }[];
  tourOpen: boolean;
  onTourToggle: () => void;
  showLimits: boolean;
  setShowLimits: (v: boolean) => void;
  showLegend: boolean;
  setShowLegend: (v: boolean) => void;
  showExport: boolean;
  setShowExport: (v: boolean) => void;
  copied: boolean;
  shareSnapshot: () => void;
  exportGraph: (format: "json" | "graphml") => void;
  renderMode: RenderMode;
  manualMode: RenderMode | null;
  setManualMode: (v: RenderMode | null) => void;
  showTables: boolean;
  onToggleTables: () => void;
  showLevel: number;
  onShowLevel: (lv: number) => void;
  showImages: boolean;
  onToggleImages: () => void;
  showEntities: boolean;
  onToggleEntities: () => void;
  graphStats: GraphStats | null;
  onExpandAll: () => void;
  onCollapseToLevel1: () => void;
  hideIsolated: boolean;
  onToggleHideIsolated: () => void;
  isolatedCount: number;
  importanceMode: boolean;
  onToggleImportance: () => void;
  domainMode: boolean;
  onToggleDomain: () => void;
  showPredictions: boolean;
  onTogglePredictions: () => void;
}

export function GraphToolbar({
  nodeFilter,
  setNodeFilter,
  edgeFilter,
  setEdgeFilter,
  searchQuery,
  handleSearch,
  searchNodeResults,
  searchDocResults,
  onSelectNodeResult,
  onSelectDocumentResult,
  docFilter,
  setDocFilter,
  docs,
  tourOpen,
  onTourToggle,
  showLimits,
  setShowLimits,
  showLegend,
  setShowLegend,
  showExport,
  setShowExport,
  copied,
  shareSnapshot,
  exportGraph,
  renderMode,
  manualMode,
  setManualMode,
  showTables,
  onToggleTables,
  showLevel,
  onShowLevel,
  showImages,
  onToggleImages,
  showEntities,
  onToggleEntities,
  graphStats,
  onExpandAll,
  onCollapseToLevel1,
  hideIsolated,
  onToggleHideIsolated,
  isolatedCount,
  importanceMode,
  onToggleImportance,
  domainMode,
  onToggleDomain,
  showPredictions,
  onTogglePredictions,
}: Props) {
  return (
    <div className="shrink-0 flex flex-col bg-gray-900 border-b border-gray-800 z-20">
      <div className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:gap-2 sm:min-h-[56px]">
        <GraphFilterPanel
          nodeFilter={nodeFilter}
          setNodeFilter={setNodeFilter}
          edgeFilter={edgeFilter}
          setEdgeFilter={setEdgeFilter}
          showTables={showTables}
          onToggleTables={onToggleTables}
        />

        <div className="hidden flex-1 min-w-4 sm:block" />

        <div className="flex flex-wrap items-center gap-2 shrink-0 sm:flex-nowrap">
          <GraphToolbarSearch
            searchQuery={searchQuery}
            handleSearch={handleSearch}
            searchNodeResults={searchNodeResults}
            searchDocResults={searchDocResults}
            onSelectNodeResult={onSelectNodeResult}
            onSelectDocumentResult={onSelectDocumentResult}
          />

          <GraphToolbarActions
            docFilter={docFilter}
            setDocFilter={setDocFilter}
            docs={docs}
            hideIsolated={hideIsolated}
            onToggleHideIsolated={onToggleHideIsolated}
            isolatedCount={isolatedCount}
            importanceMode={importanceMode}
            onToggleImportance={onToggleImportance}
            domainMode={domainMode}
            onToggleDomain={onToggleDomain}
            showPredictions={showPredictions}
            onTogglePredictions={onTogglePredictions}
            renderMode={renderMode}
            manualMode={manualMode}
            setManualMode={setManualMode}
            copied={copied}
            shareSnapshot={shareSnapshot}
            showExport={showExport}
            setShowExport={setShowExport}
            exportGraph={exportGraph}
            tourOpen={tourOpen}
            onTourToggle={onTourToggle}
            showLimits={showLimits}
            setShowLimits={setShowLimits}
            showLegend={showLegend}
            setShowLegend={setShowLegend}
          />
        </div>
      </div>
      <div className="mt-2 border-t border-gray-800/60 bg-gray-900/80">
        <GraphLevelControl
          showLevel={showLevel}
          onShowLevel={onShowLevel}
          showImages={showImages}
          onToggleImages={onToggleImages}
          showEntities={showEntities}
          onToggleEntities={onToggleEntities}
          graphStats={graphStats}
          onExpandAll={onExpandAll}
          onCollapseToLevel1={onCollapseToLevel1}
        />
      </div>
    </div>
  );
}
