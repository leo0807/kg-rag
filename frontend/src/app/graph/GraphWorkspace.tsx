"use client";

import type { Dispatch, ReactNode, RefObject, SetStateAction } from "react";
import type { EdgeFilter, GraphNode, Limits, NodeFilter, RenderMode } from "./constants";
import { type GraphTheme, MAX_SCALE, MIN_SCALE } from "./constants";
import { GraphLegend } from "./GraphLegend";
import { GraphLimitsPanel } from "./GraphLimitsPanel";
import { NodeDetailSidebar } from "./NodeDetailSidebar";

interface Props {
  containerRef: RefObject<HTMLDivElement | null>;
  svgRef: RefObject<SVGSVGElement | null>;
  canvasRef: RefObject<HTMLCanvasElement | null>;
  webglRef: RefObject<HTMLCanvasElement | null>;
  tooltipRef: RefObject<HTMLDivElement | null>;
  renderMode: RenderMode;
  filteredNodesCount: number;
  graphTheme: GraphTheme;
  heatMap: Map<string, number>;
  tour: {
    tourOpen: boolean;
    tourRunning: boolean;
    tourIdx: number;
    tourTotal: number;
    tourCurrentId: string | null;
    tourNodeIds: Set<string>;
  };
  selectedNode: GraphNode | null;
  setSelectedNode: (node: GraphNode | null) => void;
  expandingId: string | null;
  expandSection: (chunkId: string) => void;
  scale: number;
  zoomIn: () => void;
  zoomOut: () => void;
  zoomReset: () => void;
  setNodeFilter: Dispatch<SetStateAction<NodeFilter>>;
  setEdgeFilter: Dispatch<SetStateAction<EdgeFilter>>;
  showLimits: boolean;
  limits: Limits;
  setLimits: Dispatch<SetStateAction<Limits>>;
  showLegend: boolean;
  tourPanel: ReactNode;
  viewStats: {
    docCount: number;
    noRefDocCount: number;
    refEdgeCount: number;
    hiddenIsolated: number;
  };
  selectedNodeKey: string;
}

export function GraphWorkspace({
  containerRef,
  svgRef,
  canvasRef,
  webglRef,
  tooltipRef,
  renderMode,
  filteredNodesCount,
  graphTheme,
  heatMap,
  tour,
  selectedNode,
  setSelectedNode,
  expandingId,
  expandSection,
  scale,
  zoomIn,
  zoomOut,
  zoomReset,
  setNodeFilter,
  setEdgeFilter,
  showLimits,
  limits,
  setLimits,
  showLegend,
  tourPanel,
  viewStats,
  selectedNodeKey,
}: Props) {
  return (
    <div className="flex-1 flex flex-col overflow-hidden min-h-0">
      <div className="flex-1 flex overflow-hidden min-h-0">
        <div
          ref={containerRef}
          className="relative flex-1 min-w-0 overflow-hidden"
        >
          <svg
            ref={svgRef}
            className={`absolute inset-0 w-full h-full${renderMode === "svg" ? "" : " pointer-events-none opacity-0"}`}
          />
          <canvas
            ref={canvasRef}
            className={`absolute inset-0 w-full h-full${renderMode === "canvas" || renderMode === "heatmap" ? "" : " pointer-events-none opacity-0"}`}
          />
          <canvas
            ref={webglRef}
            className={`absolute inset-0 w-full h-full${renderMode === "webgl" ? "" : " pointer-events-none opacity-0"}`}
          />

          {renderMode !== "svg" && (
            <div className="absolute top-3 left-3 px-2 py-1 bg-gray-900/80 border border-indigo-700/40 rounded-lg text-xs text-indigo-400 pointer-events-none z-10">
              {renderMode === "webgl" &&
                `WebGL 模式 · ${filteredNodesCount} 节点`}
              {renderMode === "canvas" &&
                `Canvas 模式 · ${filteredNodesCount} 节点`}
              {renderMode === "heatmap" &&
                `热力图模式 · ${filteredNodesCount} 节点（按文档聚类）`}
            </div>
          )}

          {showLegend && (
            <GraphLegend heatMap={heatMap} tourOpen={tour.tourOpen} />
          )}

          <div className="absolute bottom-4 left-3 pointer-events-none z-10 flex flex-col gap-0.5">
            <span className="text-[11px] text-gray-600">
              {viewStats.docCount} 文档
            </span>
            {viewStats.hiddenIsolated > 0 && (
              <span className="text-[11px] text-gray-600">
                已隐藏 {viewStats.hiddenIsolated} 孤立
              </span>
            )}
            {viewStats.refEdgeCount > 0 && (
              <span className="text-[11px] text-gray-600">
                {viewStats.refEdgeCount} 引用关系
              </span>
            )}
            {viewStats.noRefDocCount > 0 && (
              <span className="text-[11px] text-gray-600">
                {viewStats.noRefDocCount} 无引用文档
              </span>
            )}
          </div>

          {tour.tourOpen && tour.tourRunning && tour.tourIdx >= 0 && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 bg-gray-900/90 border border-amber-500/40 rounded-full px-4 py-1.5 flex items-center gap-2 backdrop-blur-sm">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shrink-0" />
              <span className="text-xs text-amber-300 font-medium">
                漫游中 · 第 {tour.tourIdx + 1}/{tour.tourTotal} 站
              </span>
            </div>
          )}

          <div className="absolute bottom-4 right-4 flex items-center gap-2">
            <span className="text-xs text-gray-600 mr-1">
              拖拽平移 · 滚轮缩放
            </span>
            <button
              type="button"
              onClick={zoomOut}
              disabled={scale <= MIN_SCALE}
              className="w-7 h-7 rounded bg-gray-800 text-gray-100 text-sm hover:bg-gray-700 disabled:opacity-30 flex items-center justify-center"
            >
              −
            </button>
            <button
              type="button"
              onClick={() => {
                zoomReset();
                setNodeFilter("全部");
                setEdgeFilter("全部关系");
              }}
              className="px-2 h-7 rounded bg-gray-800 text-xs text-gray-300 hover:bg-gray-700"
            >
              重置
            </button>
            <button
              type="button"
              onClick={zoomIn}
              disabled={scale >= MAX_SCALE}
              className="w-7 h-7 rounded bg-gray-800 text-gray-100 text-sm hover:bg-gray-700 disabled:opacity-30 flex items-center justify-center"
            >
              +
            </button>
          </div>

          <div ref={tooltipRef} className={graphTheme.tooltipClassName} />
        </div>

        {(showLimits || selectedNode) && (
          <aside className="w-80 shrink-0 flex flex-col overflow-hidden border-l border-gray-800 bg-gray-950">
            {showLimits && (
              <div className="p-3 border-b border-gray-800">
                <GraphLimitsPanel limits={limits} setLimits={setLimits} />
              </div>
            )}
            {selectedNode && (
              <NodeDetailSidebar
                key={selectedNodeKey}
                node={selectedNode}
                onClose={() => setSelectedNode(null)}
                onExpandSection={expandSection}
                expandingId={expandingId}
              />
            )}
          </aside>
        )}
      </div>

      {tourPanel}
    </div>
  );
}
