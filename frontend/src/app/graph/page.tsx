"use client";

import { useRef } from "react";
import { GraphToolbar } from "./GraphToolbar";
import { GraphWorkspace } from "./GraphWorkspace";
import { TourPanel } from "./TourPanel";
import { useGraphPage } from "./useGraphPage";

export default function GraphPage() {
  const svgRef = useRef<SVGSVGElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const webglRef = useRef<HTMLCanvasElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const {
    containerRef,
    filteredNodesRef,
    renderMode,
    manualMode,
    setManualMode,
    scale,
    graphStats,
    heatMap,
    nodeFilter,
    setNodeFilter,
    edgeFilter,
    setEdgeFilter,
    selectedNode,
    setSelectedNode,
    searchQuery,
    docFilter,
    setDocFilter,
    docs,
    docSearchResults,
    nodeSearchResults,
    limits,
    setLimits,
    expandingId,
    showLimits,
    setShowLimits,
    showLegend,
    setShowLegend,
    showExport,
    setShowExport,
    copied,
    hideIsolated,
    setHideIsolated,
    viewStats,
    importanceMode,
    setImportanceMode,
    domainMode,
    setDomainMode,
    graphTheme,
    tour,
    zoomIn,
    zoomOut,
    zoomReset,
    handleSearch,
    handleSelectNodeResult,
    handleSelectDocumentResult,
    expandSection,
    exportGraph,
    shareSnapshot,
    onExpandAll,
    showPredictions,
    setShowPredictions,
  } = useGraphPage({ svgRef, canvasRef, webglRef, tooltipRef });

  return (
    <div className="flex h-full w-full select-none flex-col bg-gray-950">
      <GraphToolbar
        nodeFilter={nodeFilter}
        setNodeFilter={setNodeFilter}
        edgeFilter={edgeFilter}
        setEdgeFilter={setEdgeFilter}
        searchQuery={searchQuery}
        handleSearch={handleSearch}
        searchNodeResults={nodeSearchResults}
        searchDocResults={docSearchResults}
        onSelectNodeResult={handleSelectNodeResult}
        onSelectDocumentResult={handleSelectDocumentResult}
        docFilter={docFilter}
        setDocFilter={setDocFilter}
        docs={docs}
        tourOpen={tour.tourOpen}
        onTourToggle={() => {
          tour.setTourOpen((v) => !v);
          if (tour.tourRunning) tour.stopTour();
        }}
        showLimits={showLimits}
        setShowLimits={setShowLimits}
        showLegend={showLegend}
        setShowLegend={setShowLegend}
        showExport={showExport}
        setShowExport={setShowExport}
        copied={copied}
        shareSnapshot={shareSnapshot}
        exportGraph={exportGraph}
        renderMode={renderMode}
        manualMode={manualMode}
        setManualMode={setManualMode}
        showTables={limits.tbl > 0}
        onToggleTables={() =>
          setLimits((prev) => ({
            ...prev,
            tbl: prev.tbl > 0 ? 0 : 200,
          }))
        }
        showLevel={limits.show_level}
        onShowLevel={(lv) => setLimits((prev) => ({ ...prev, show_level: lv }))}
        showImages={limits.show_images}
        onToggleImages={() =>
          setLimits((prev) => ({ ...prev, show_images: !prev.show_images }))
        }
        showEntities={limits.show_entities}
        onToggleEntities={() =>
          setLimits((prev) => ({
            ...prev,
            show_entities: !prev.show_entities,
          }))
        }
        graphStats={graphStats}
        onExpandAll={() =>
          onExpandAll(
            docFilter,
            limits.show_images,
            limits.show_entities,
            graphStats?.total ?? 0,
          )
        }
        onCollapseToLevel1={() =>
          setLimits((prev) => ({ ...prev, show_level: 1 }))
        }
        hideIsolated={hideIsolated}
        onToggleHideIsolated={() => setHideIsolated((v) => !v)}
        isolatedCount={viewStats.hiddenIsolated}
        importanceMode={importanceMode}
        onToggleImportance={() => {
          setImportanceMode((v) => !v);
          if (domainMode) setDomainMode(false);
        }}
        domainMode={domainMode}
        onToggleDomain={() => {
          setDomainMode((v) => !v);
          if (importanceMode) setImportanceMode(false);
        }}
        showPredictions={showPredictions}
        onTogglePredictions={() => setShowPredictions((v) => !v)}
      />

      <GraphWorkspace
        containerRef={containerRef}
        svgRef={svgRef}
        canvasRef={canvasRef}
        webglRef={webglRef}
        tooltipRef={tooltipRef}
        loading={graphStats === null}
        renderMode={renderMode}
        filteredNodesCount={filteredNodesRef.current.length}
        graphTheme={graphTheme}
        heatMap={heatMap}
        tour={tour}
        selectedNode={selectedNode}
        setSelectedNode={setSelectedNode}
        expandingId={expandingId}
        expandSection={expandSection}
        scale={scale}
        zoomIn={zoomIn}
        zoomOut={zoomOut}
        zoomReset={zoomReset}
        setNodeFilter={setNodeFilter}
        setEdgeFilter={setEdgeFilter}
        showLimits={showLimits}
        limits={limits}
        setLimits={setLimits}
        showLegend={showLegend}
        viewStats={viewStats}
        selectedNodeKey={selectedNode?.id || ""}
        tourPanel={
          tour.tourOpen ? (
            <TourPanel
              tourTopic={tour.tourTopic}
              setTourTopic={tour.setTourTopic}
              tourRunning={tour.tourRunning}
              tourStops={tour.tourStops}
              tourIdx={tour.tourIdx}
              tourTotal={tour.tourTotal}
              tourText={tour.tourText}
              tourStreaming={tour.tourStreaming}
              hasPrev={tour.hasPrev}
              hasNext={tour.hasNext}
              onStart={tour.startTour}
              onStop={tour.stopTour}
              onNavigate={tour.navigateTour}
              onClose={() => {
                tour.setTourOpen(false);
                if (tour.tourRunning) tour.stopTour();
              }}
            />
          ) : null
        }
      />
    </div>
  );
}
