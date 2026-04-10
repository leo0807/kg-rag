"use client";

import { Settings, Search, Download, Layers, Share2, Check, Compass } from "lucide-react";
import { NodeFilter, EdgeFilter, RenderMode, NODE_COLOR, NODE_SHORT, NODE_TYPES, EDGE_TYPES } from "./constants";

interface Props {
    nodeFilter:    NodeFilter;
    setNodeFilter: (v: NodeFilter) => void;
    edgeFilter:    EdgeFilter;
    setEdgeFilter: (v: EdgeFilter) => void;
    searchQuery:   string;
    handleSearch:  (q: string) => void;
    docFilter:     string;
    setDocFilter:  (v: string) => void;
    docs:          { doc_id: string; title: string }[];
    tourOpen:      boolean;
    onTourToggle:  () => void;
    showLimits:    boolean;
    setShowLimits: (v: boolean) => void;
    showLegend:    boolean;
    setShowLegend: (v: boolean) => void;
    showExport:    boolean;
    setShowExport: (v: boolean) => void;
    copied:        boolean;
    shareSnapshot: () => void;
    exportGraph:   (format: "json" | "graphml") => void;
    renderMode:    RenderMode;
    manualMode:    RenderMode | null;
    setManualMode: (v: RenderMode | null) => void;
}

export function GraphToolbar({
    nodeFilter, setNodeFilter, edgeFilter, setEdgeFilter,
    searchQuery, handleSearch, docFilter, setDocFilter, docs,
    tourOpen, onTourToggle,
    showLimits, setShowLimits, showLegend, setShowLegend,
    showExport, setShowExport,
    copied, shareSnapshot, exportGraph,
    renderMode, manualMode, setManualMode,
}: Props) {
    return (
        <div className="shrink-0 flex items-center gap-1.5 px-3 h-11 bg-gray-900 border-b border-gray-800 z-20">
            {/* Node type filter */}
            <div className="flex items-center gap-0.5">
                {NODE_TYPES.map(type => (
                    <button key={type} onClick={() => setNodeFilter(type)} title={type}
                        className={`flex items-center gap-1 px-2 h-7 rounded text-xs font-medium transition-colors whitespace-nowrap ${
                            nodeFilter === type ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white hover:bg-gray-800"
                        }`}>
                        {type !== "全部" && (
                            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: NODE_COLOR[type] }} />
                        )}
                        {NODE_SHORT[type]}
                    </button>
                ))}
            </div>

            <div className="w-px h-5 bg-gray-700 mx-0.5 shrink-0" />

            {/* Edge type filter */}
            <select value={edgeFilter} onChange={e => setEdgeFilter(e.target.value as EdgeFilter)}
                className="h-7 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300 outline-none focus:border-indigo-500 max-w-[138px]">
                {EDGE_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>

            <div className="flex-1" />

            {/* Search */}
            <div className="relative">
                <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                <input value={searchQuery} onChange={e => handleSearch(e.target.value)}
                    placeholder="搜索节点…"
                    className="pl-6 pr-2 h-7 w-28 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500" />
            </div>

            {/* Doc filter */}
            <select value={docFilter} onChange={e => setDocFilter(e.target.value)}
                className="h-7 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-400 outline-none focus:border-indigo-500 max-w-[110px]">
                <option value="">全部文档</option>
                {docs.map(d => <option key={d.doc_id} value={d.doc_id}>{d.doc_id}</option>)}
            </select>

            <div className="w-px h-5 bg-gray-700 mx-0.5 shrink-0" />

            {/* Render mode */}
            <div className="flex items-center gap-0.5 bg-gray-800/60 rounded px-0.5 py-0.5">
                {(["svg", "canvas", "webgl"] as const).map(m => (
                    <button key={m} onClick={() => setManualMode(manualMode === m ? null : m)}
                        title={m === "svg" ? "SVG（少量节点）" : m === "canvas" ? "Canvas（中量）" : "WebGL（海量）"}
                        className={`px-1.5 h-5 rounded text-xs font-mono transition-colors ${
                            renderMode === m ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-gray-300"
                        }`}>
                        {m === "svg" ? "SVG" : m === "canvas" ? "2D" : "3D"}
                    </button>
                ))}
            </div>

            <div className="w-px h-5 bg-gray-700 mx-0.5 shrink-0" />

            {/* Tour */}
            <button onClick={onTourToggle}
                className={`flex items-center gap-1 px-2 h-7 rounded text-xs font-medium transition-colors ${
                    tourOpen ? "bg-amber-500 text-gray-950" : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`} title="图谱漫游">
                <Compass size={13} />
                {!tourOpen && <span className="hidden sm:inline">漫游</span>}
            </button>

            {/* Settings */}
            <button onClick={() => { setShowLimits(!showLimits); setShowLegend(false); }}
                className={`p-1.5 rounded transition-colors ${showLimits ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"}`}
                title="节点数量">
                <Settings size={14} />
            </button>

            {/* Legend */}
            <button onClick={() => { setShowLegend(!showLegend); setShowLimits(false); }}
                className={`p-1.5 rounded transition-colors ${showLegend ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"}`}
                title="图例">
                <Layers size={14} />
            </button>

            {/* Share */}
            <button onClick={shareSnapshot}
                className={`p-1.5 rounded transition-colors ${copied ? "bg-emerald-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"}`}
                title="复制分享链接">
                {copied ? <Check size={14} /> : <Share2 size={14} />}
            </button>

            {/* Export */}
            <div className="relative" onClick={e => e.stopPropagation()}>
                <button onClick={() => setShowExport(!showExport)}
                    className={`p-1.5 rounded transition-colors ${showExport ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"}`}
                    title="导出">
                    <Download size={14} />
                </button>
                {showExport && (
                    <div className="absolute right-0 top-full mt-1 bg-gray-900 border border-gray-700 rounded-lg py-1 w-28 shadow-xl z-30">
                        <button onClick={() => { exportGraph("json"); setShowExport(false); }}
                            className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800">导出 JSON</button>
                        <button onClick={() => { exportGraph("graphml"); setShowExport(false); }}
                            className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800">导出 GraphML</button>
                    </div>
                )}
            </div>
        </div>
    );
}
