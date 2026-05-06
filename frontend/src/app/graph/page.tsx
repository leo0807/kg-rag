"use client";

import { useRef } from "react";
import { MIN_SCALE, MAX_SCALE } from "./constants";
import { NodeDetailSidebar } from "./NodeDetailSidebar";
import { GraphToolbar } from "./GraphToolbar";
import { TourPanel } from "./TourPanel";
import { GraphLegend } from "./GraphLegend";
import { GraphLimitsPanel } from "./GraphLimitsPanel";
import { useGraphPage } from "./useGraphPage";

export default function GraphPage() {
  const svgRef = useRef<SVGSVGElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const webglRef = useRef<HTMLCanvasElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const {
    containerRef, filteredNodesRef,
    renderMode, manualMode, setManualMode, scale,
    graphStats, heatMap,
    nodeFilter, setNodeFilter, edgeFilter, setEdgeFilter,
    selectedNode, setSelectedNode, searchQuery,
    docFilter, setDocFilter, docs,
    docSearchResults, nodeSearchResults,
    limits, setLimits, expandingId,
    showLimits, setShowLimits, showLegend, setShowLegend,
    showExport, setShowExport, copied,
    hideIsolated, setHideIsolated, viewStats,
    importanceMode, setImportanceMode, domainMode, setDomainMode,
    graphTheme, tour,
    zoomIn, zoomOut, zoomReset,
    handleSearch, handleSelectNodeResult, handleSelectDocumentResult,
    expandSection, exportGraph, shareSnapshot, onExpandAll,
    showPredictions, setShowPredictions,
  } = useGraphPage({ svgRef, canvasRef, webglRef, tooltipRef });

  return (
    <div
      className="w-full h-full bg-gray-950 select-none flex flex-col"
      onClick={() => { if (showExport) setShowExport(false); }}
    >
      <GraphToolbar
        nodeFilter={nodeFilter} setNodeFilter={setNodeFilter}
        edgeFilter={edgeFilter} setEdgeFilter={setEdgeFilter}
        searchQuery={searchQuery} handleSearch={handleSearch}
        searchNodeResults={nodeSearchResults} searchDocResults={docSearchResults}
        onSelectNodeResult={handleSelectNodeResult} onSelectDocumentResult={handleSelectDocumentResult}
        docFilter={docFilter} setDocFilter={setDocFilter} docs={docs}
        tourOpen={tour.tourOpen}
        onTourToggle={() => { tour.setTourOpen((v) => !v); if (tour.tourRunning) tour.stopTour(); }}
        showLimits={showLimits} setShowLimits={setShowLimits}
        showLegend={showLegend} setShowLegend={setShowLegend}
        showExport={showExport} setShowExport={setShowExport}
        copied={copied} shareSnapshot={shareSnapshot} exportGraph={exportGraph}
        renderMode={renderMode} manualMode={manualMode} setManualMode={setManualMode}
        showTables={limits.tbl > 0} onToggleTables={() => setLimits((prev) => ({ ...prev, tbl: prev.tbl > 0 ? 0 : 200 }))}
        showLevel={limits.show_level} onShowLevel={(lv) => setLimits((prev) => ({ ...prev, show_level: lv }))}
        showImages={limits.show_images} onToggleImages={() => setLimits((prev) => ({ ...prev, show_images: !prev.show_images }))}
        showEntities={limits.show_entities} onToggleEntities={() => setLimits((prev) => ({ ...prev, show_entities: !prev.show_entities }))}
        graphStats={graphStats}
        onExpandAll={() => onExpandAll(docFilter, limits.show_images, limits.show_entities, graphStats?.total ?? 0)}
        onCollapseToLevel1={() => setLimits((prev) => ({ ...prev, show_level: 1 }))}
        hideIsolated={hideIsolated}
        onToggleHideIsolated={() => setHideIsolated((v) => !v)}
        isolatedCount={viewStats.hiddenIsolated}
        importanceMode={importanceMode}
        onToggleImportance={() => { setImportanceMode(v => !v); if (domainMode) setDomainMode(false); }}
        domainMode={domainMode}
        onToggleDomain={() => { setDomainMode(v => !v); if (importanceMode) setImportanceMode(false); }}
        showPredictions={showPredictions}
        onTogglePredictions={() => setShowPredictions(v => !v)}
      />

      <div className="flex-1 flex flex-col overflow-hidden min-h-0">
        <div className="flex-1 flex overflow-hidden min-h-0">
          <div ref={containerRef} className="relative flex-1 overflow-hidden">
            <svg ref={svgRef} className={`absolute inset-0 w-full h-full${renderMode === "svg" ? "" : " pointer-events-none opacity-0"}`} />
            <canvas ref={canvasRef} className={`absolute inset-0 w-full h-full${renderMode === "canvas" || renderMode === "heatmap" ? "" : " pointer-events-none opacity-0"}`} />
            <canvas ref={webglRef} className={`absolute inset-0 w-full h-full${renderMode === "webgl" ? "" : " pointer-events-none opacity-0"}`} />

            {renderMode !== "svg" && (
              <div className="absolute top-3 left-3 px-2 py-1 bg-gray-900/80 border border-indigo-700/40 rounded-lg text-xs text-indigo-400 pointer-events-none z-10">
                {renderMode === "webgl" && `WebGL 模式 · ${filteredNodesRef.current.length} 节点`}
                {renderMode === "canvas" && `Canvas 模式 · ${filteredNodesRef.current.length} 节点`}
                {renderMode === "heatmap" && `热力图模式 · ${filteredNodesRef.current.length} 节点（按文档聚类）`}
              </div>
            )}

            {showLimits && <GraphLimitsPanel limits={limits} setLimits={setLimits} />}
            {showLegend && <GraphLegend heatMap={heatMap} tourOpen={tour.tourOpen} />}

            {/* Stats overlay */}
            <div className="absolute bottom-4 left-3 pointer-events-none z-10 flex flex-col gap-0.5">
              <span className="text-[11px] text-gray-600">{viewStats.docCount} 文档</span>
              {viewStats.hiddenIsolated > 0 && (
                <span className="text-[11px] text-gray-600">已隐藏 {viewStats.hiddenIsolated} 孤立</span>
              )}
              {viewStats.refEdgeCount > 0 && (
                <span className="text-[11px] text-gray-600">{viewStats.refEdgeCount} 引用关系</span>
              )}
              {viewStats.noRefDocCount > 0 && (
                <span className="text-[11px] text-gray-600">{viewStats.noRefDocCount} 无引用文档</span>
              )}
            </div>

            {tour.tourOpen && tour.tourRunning && tour.tourIdx >= 0 && (
              <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 bg-gray-900/90 border border-amber-500/40 rounded-full px-4 py-1.5 flex items-center gap-2 backdrop-blur-sm">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shrink-0" />
                <span className="text-xs text-amber-300 font-medium">漫游中 · 第 {tour.tourIdx + 1}/{tour.tourTotal} 站</span>
              </div>
            )}

            <div className="absolute bottom-4 right-4 flex items-center gap-2">
              <span className="text-xs text-gray-600 mr-1">拖拽平移 · 滚轮缩放</span>
              <button onClick={zoomOut} disabled={scale <= MIN_SCALE} className="w-7 h-7 rounded bg-gray-800 text-gray-100 text-sm hover:bg-gray-700 disabled:opacity-30 flex items-center justify-center">−</button>
              <button onClick={() => { zoomReset(); setNodeFilter("全部"); setEdgeFilter("全部关系"); }} className="px-2 h-7 rounded bg-gray-800 text-xs text-gray-300 hover:bg-gray-700">重置</button>
              <button onClick={zoomIn} disabled={scale >= MAX_SCALE} className="w-7 h-7 rounded bg-gray-800 text-gray-100 text-sm hover:bg-gray-700 disabled:opacity-30 flex items-center justify-center">+</button>
            </div>

            <div ref={tooltipRef} className={graphTheme.tooltipClassName} />
          </div>

          {selectedNode && (
            <NodeDetailSidebar node={selectedNode} onClose={() => setSelectedNode(null)} onExpandSection={expandSection} expandingId={expandingId} />
          )}
        </div>

        {tour.tourOpen && (
          <TourPanel
            tourTopic={tour.tourTopic} setTourTopic={tour.setTourTopic}
            tourRunning={tour.tourRunning} tourStops={tour.tourStops}
            tourIdx={tour.tourIdx} tourTotal={tour.tourTotal}
            tourText={tour.tourText} tourStreaming={tour.tourStreaming}
            hasPrev={tour.hasPrev} hasNext={tour.hasNext}
            onStart={tour.startTour} onStop={tour.stopTour} onNavigate={tour.navigateTour}
            onClose={() => { tour.setTourOpen(false); if (tour.tourRunning) tour.stopTour(); }}
          />
        )}
      </div>
    </div>
  );
}
