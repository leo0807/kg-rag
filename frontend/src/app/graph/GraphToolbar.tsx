"use client";

import { useState } from "react";
import {
  Settings,
  Search,
  Download,
  Layers,
  Share2,
  Check,
  Compass,
  ChevronDown,
  ChevronUp,
  Eye,
  EyeOff,
  FileText,
  CircleDot,
} from "lucide-react";
import {
  type GraphNode,
  type NodeFilter,
  type EdgeFilter,
  type RenderMode,
  NODE_COLOR,
  NODE_SHORT,
  NODE_TYPES,
  EDGE_TYPES,
  type GraphStats,
} from "./constants";

interface SearchDocumentResult {
  doc_id: string;
  title: string;
}

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
  // 新增：分层控制
  showLevel: number;
  onShowLevel: (lv: number) => void;
  showImages: boolean;
  onToggleImages: () => void;
  showEntities: boolean;
  onToggleEntities: () => void;
  graphStats: GraphStats | null;
  onExpandAll: () => void;
  onCollapseToLevel1: () => void;
}

const LEVEL_LABELS: Record<number, string> = {
  0: "全部",
  1: "1级",
  2: "2级",
  3: "3级",
  4: "4级",
};

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
}: Props) {
  const [searchFocused, setSearchFocused] = useState(false);
  const showSearchDropdown = searchFocused && searchQuery.trim().length > 0;
  const hasSearchResults =
    searchNodeResults.length > 0 || searchDocResults.length > 0;

  return (
    <div className="shrink-0 flex flex-col bg-gray-900 border-b border-gray-800 z-20">
      {/* 主工具栏行 */}
      <div className="flex items-center gap-1.5 px-3 h-11">
        {/* Node type filter */}
        <div className="flex items-center gap-0.5">
          {NODE_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => setNodeFilter(type)}
              title={type}
              className={`flex items-center gap-1 px-2 h-7 rounded text-xs font-medium transition-colors whitespace-nowrap ${
                nodeFilter === type
                  ? "bg-indigo-600 text-white"
                  : "text-gray-400 hover:text-gray-100 hover:bg-gray-800"
              }`}
            >
              {type !== "全部" && (
                <span
                  className="w-1.5 h-1.5 rounded-full shrink-0"
                  style={{ backgroundColor: NODE_COLOR[type] }}
                />
              )}
              {NODE_SHORT[type]}
            </button>
          ))}
        </div>

        {/* Table toggle */}
        <button
          type="button"
          onClick={onToggleTables}
          title={showTables ? "隐藏表格节点" : "显示表格节点（默认关闭）"}
          className={`flex items-center gap-1 px-2 h-7 rounded text-xs font-medium transition-colors ${
            showTables
              ? "bg-green-600 text-white"
              : "text-gray-500 hover:text-gray-100 hover:bg-gray-800 border border-dashed border-gray-700"
          }`}
        >
          <span
            className="w-1.5 h-1.5 rounded-full shrink-0"
            style={{ backgroundColor: "#22c55e" }}
          />
          表格
        </button>

        <div className="w-px h-5 bg-gray-700 mx-0.5 shrink-0" />

        {/* Edge type filter */}
        <select
          value={edgeFilter}
          onChange={(e) => setEdgeFilter(e.target.value as EdgeFilter)}
          className="h-7 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300 outline-none focus:border-indigo-500 max-w-[138px]"
        >
          {EDGE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <div className="flex-1" />

        {/* Search */}
        <div className="relative">
          <Search
            size={12}
            className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
          />
          <input
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => window.setTimeout(() => setSearchFocused(false), 120)}
            placeholder="搜索节点或文档…"
            className="pl-6 pr-2 h-7 w-44 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500"
          />
          {showSearchDropdown && (
            <div className="absolute right-0 top-full mt-1 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-gray-700 bg-gray-900 shadow-2xl z-30">
              {searchNodeResults.length > 0 && (
                <div className="border-b border-gray-800/80 px-2 py-2">
                  <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-gray-500">
                    节点
                  </div>
                  <div className="space-y-1">
                    {searchNodeResults.map((node) => (
                      <button
                        key={node.id}
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          onSelectNodeResult(node);
                          setSearchFocused(false);
                        }}
                        className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-gray-800"
                      >
                        <CircleDot
                          size={13}
                          className="mt-0.5 shrink-0 text-indigo-400"
                        />
                        <div className="min-w-0">
                          <div className="truncate text-xs font-medium text-gray-100">
                            {node.name || node.id}
                          </div>
                          <div className="truncate text-[11px] text-gray-500">
                            {node.type || node.label || "节点"}
                            {node.doc_id ? ` · ${node.doc_id}` : ""}
                            {node.number ? ` · §${node.number}` : ""}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {searchDocResults.length > 0 && (
                <div className="px-2 py-2">
                  <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-gray-500">
                    文档
                  </div>
                  <div className="space-y-1">
                    {searchDocResults.map((doc) => (
                      <button
                        key={doc.doc_id}
                        type="button"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          onSelectDocumentResult(doc);
                          setSearchFocused(false);
                        }}
                        className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-gray-800"
                      >
                        <FileText
                          size={13}
                          className="mt-0.5 shrink-0 text-emerald-400"
                        />
                        <div className="min-w-0">
                          <div className="truncate text-xs font-medium text-gray-100">
                            {doc.doc_id}
                          </div>
                          <div className="truncate text-[11px] text-gray-500">
                            {doc.title || "未命名文档"}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {!hasSearchResults && (
                <div className="px-3 py-2 text-xs text-gray-500">
                  没有匹配的节点或文档
                </div>
              )}
            </div>
          )}
        </div>

        {/* Doc filter */}
        <select
          value={docFilter}
          onChange={(e) => setDocFilter(e.target.value)}
          className="h-7 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-400 outline-none focus:border-indigo-500 max-w-[110px]"
        >
          <option value="">全部文档</option>
          {docs.map((d) => (
            <option key={d.doc_id} value={d.doc_id}>
              {d.doc_id}
            </option>
          ))}
        </select>

        <div className="w-px h-5 bg-gray-700 mx-0.5 shrink-0" />

        {/* Render mode */}
        <div className="flex items-center gap-0.5 bg-gray-800/60 rounded px-0.5 py-0.5">
          {(["svg", "canvas", "webgl"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setManualMode(manualMode === m ? null : m)}
              title={
                m === "svg"
                  ? "SVG（少量节点）"
                  : m === "canvas"
                    ? "Canvas（中量）"
                    : "WebGL（海量）"
              }
              className={`px-1.5 h-5 rounded text-xs font-mono transition-colors ${
                renderMode === m
                  ? "bg-indigo-600 text-white"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {m === "svg" ? "SVG" : m === "canvas" ? "2D" : "3D"}
            </button>
          ))}
        </div>

        <div className="w-px h-5 bg-gray-700 mx-0.5 shrink-0" />

        {/* Tour */}
        <button
          type="button"
          onClick={onTourToggle}
          className={`flex items-center gap-1 px-2 h-7 rounded text-xs font-medium transition-colors ${
            tourOpen
              ? "bg-amber-500 text-gray-950"
              : "text-gray-400 hover:text-gray-100 hover:bg-gray-800"
          }`}
          title="图谱漫游"
        >
          <Compass size={13} />
          {!tourOpen && <span className="hidden sm:inline">漫游</span>}
        </button>

        {/* Settings */}
        <button
          type="button"
          onClick={() => {
            setShowLimits(!showLimits);
            setShowLegend(false);
          }}
          className={`p-1.5 rounded transition-colors ${showLimits ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-gray-100 hover:bg-gray-800"}`}
          title="节点数量"
        >
          <Settings size={14} />
        </button>

        {/* Legend */}
        <button
          type="button"
          onClick={() => {
            setShowLegend(!showLegend);
            setShowLimits(false);
          }}
          className={`p-1.5 rounded transition-colors ${showLegend ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-gray-100 hover:bg-gray-800"}`}
          title="图例"
        >
          <Layers size={14} />
        </button>

        {/* Share */}
        <button
          type="button"
          onClick={shareSnapshot}
          className={`p-1.5 rounded transition-colors ${copied ? "bg-emerald-600 text-white" : "text-gray-500 hover:text-gray-100 hover:bg-gray-800"}`}
          title="复制分享链接"
        >
          {copied ? <Check size={14} /> : <Share2 size={14} />}
        </button>

        {/* Export */}
        <div className="relative">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setShowExport(!showExport);
            }}
            className={`p-1.5 rounded transition-colors ${showExport ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-gray-100 hover:bg-gray-800"}`}
            title="导出"
          >
            <Download size={14} />
          </button>
          {showExport && (
            <div
              className="absolute right-0 top-full mt-1 bg-gray-900 border border-gray-700 rounded-lg py-1 w-28 shadow-xl z-30"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                onClick={() => {
                  exportGraph("json");
                  setShowExport(false);
                }}
                className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800"
              >
                导出 JSON
              </button>
              <button
                type="button"
                onClick={() => {
                  exportGraph("graphml");
                  setShowExport(false);
                }}
                className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800"
              >
                导出 GraphML
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 分层控制行 */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-t border-gray-800/60 bg-gray-900/80">
        {/* 章节深度选择器 */}
        <span className="text-xs text-gray-600 shrink-0">章节深度</span>
        <div className="flex items-center gap-0.5">
          {[0, 1, 2, 3, 4].map((lv) => (
            <button
              key={lv}
              type="button"
              onClick={() => onShowLevel(lv)}
              className={`px-2 h-6 rounded text-xs font-medium transition-colors ${
                showLevel === lv
                  ? "bg-amber-500 text-gray-950 font-semibold"
                  : "text-gray-500 hover:text-gray-100 hover:bg-gray-800"
              }`}
            >
              {LEVEL_LABELS[lv]}
            </button>
          ))}
        </div>

        <div className="w-px h-4 bg-gray-700 mx-1 shrink-0" />

        {/* 图片/实体切换 */}
        <button
          type="button"
          onClick={onToggleImages}
          title={showImages ? "隐藏图片节点" : "显示图片节点"}
          className={`flex items-center gap-1 px-2 h-6 rounded text-xs transition-colors ${
            showImages
              ? "text-pink-400 bg-pink-950/30"
              : "text-gray-600 hover:text-gray-300 hover:bg-gray-800"
          }`}
        >
          {showImages ? <Eye size={11} /> : <EyeOff size={11} />}
          图片
        </button>
        <button
          type="button"
          onClick={onToggleEntities}
          title={showEntities ? "隐藏实体节点" : "显示实体节点"}
          className={`flex items-center gap-1 px-2 h-6 rounded text-xs transition-colors ${
            showEntities
              ? "text-emerald-400 bg-emerald-950/30"
              : "text-gray-600 hover:text-gray-300 hover:bg-gray-800"
          }`}
        >
          {showEntities ? <Eye size={11} /> : <EyeOff size={11} />}
          实体
        </button>

        <div className="w-px h-4 bg-gray-700 mx-1 shrink-0" />

        {/* 展开/收起按钮 */}
        <button
          type="button"
          onClick={onExpandAll}
          className="flex items-center gap-1 px-2 h-6 rounded text-xs text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors"
        >
          <ChevronDown size={11} />
          展开全部
        </button>
        <button
          type="button"
          onClick={onCollapseToLevel1}
          className="flex items-center gap-1 px-2 h-6 rounded text-xs text-gray-400 hover:text-gray-100 hover:bg-gray-800 transition-colors"
        >
          <ChevronUp size={11} />
          收起到一级
        </button>

        <div className="flex-1" />

        {/* 节点统计 */}
        {graphStats && (
          <div className="flex items-center gap-2 text-xs text-gray-600">
            <span>文档 {graphStats.docs}</span>
            <span>·</span>
            <span>章节 {graphStats.sections}</span>
            {graphStats.images > 0 && (
              <>
                <span>·</span>
                <span>图片 {graphStats.images}</span>
              </>
            )}
            {graphStats.tables > 0 && (
              <>
                <span>·</span>
                <span>表格 {graphStats.tables}</span>
              </>
            )}
            {graphStats.entities > 0 && (
              <>
                <span>·</span>
                <span>实体 {graphStats.entities}</span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
