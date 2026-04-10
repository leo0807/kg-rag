"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import {
    GraphNode, GraphData, NodeFilter, EdgeFilter, RenderMode, Limits,
    MIN_SCALE, MAX_SCALE, NODE_COLOR,
} from "./constants";
import { drawGraph }         from "./renderSVG";
import { drawGraphCanvas }   from "./renderCanvas";
import { drawGraphHeatmap }  from "./renderHeatmap";
import { drawGraphWebGL }    from "./renderWebGL";
import { NodeDetailSidebar } from "./NodeDetailSidebar";
import { GraphToolbar }      from "./GraphToolbar";
import { TourPanel }         from "./TourPanel";
import { useTour }           from "./useTour";

export default function GraphPage() {
    const svgRef         = useRef<SVGSVGElement>(null);
    const canvasRef      = useRef<HTMLCanvasElement>(null);
    const webglRef       = useRef<HTMLCanvasElement>(null);
    const tooltipRef     = useRef<HTMLDivElement>(null);
    const zoomRef        = useRef<any>(null);
    const pixiDestroyRef = useRef<(() => void) | null>(null);
    const filteredNodesRef = useRef<GraphNode[]>([]);
    const filteredEdgesRef = useRef<any[]>([]);

    const [renderMode,  setRenderMode]       = useState<RenderMode>("svg");
    const [manualMode,  setManualMode]       = useState<RenderMode | null>(null);
    const [data,       setData]             = useState<GraphData | null>(null);
    const [heatMap,    setHeatMap]          = useState<Map<string, number>>(new Map());
    const [scale,      setScale]            = useState(1);
    const [nodeFilter, setNodeFilter]       = useState<NodeFilter>("全部");
    const [edgeFilter, setEdgeFilter]       = useState<EdgeFilter>("全部关系");
    const [selectedNode, setSelectedNode]   = useState<GraphNode | null>(null);
    const [searchQuery,  setSearchQuery]    = useState("");
    const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());
    const [docFilter,  setDocFilter]        = useState("");
    const [docs,       setDocs]             = useState<{doc_id: string; title: string}[]>([]);
    const [limits,     setLimits]           = useState<Limits>({ doc: 50, sec: 200, entity: 100 });
    const [showLimits, setShowLimits]       = useState(false);
    const [showLegend, setShowLegend]       = useState(false);
    const [showExport, setShowExport]       = useState(false);
    const [copied,     setCopied]           = useState(false);

    function activeEl() {
        if (renderMode === "webgl") return webglRef.current as Element | null;
        if (renderMode === "svg")   return svgRef.current   as Element | null;
        return canvasRef.current as Element | null;
    }
    function zoomIn()    { const el = activeEl(); if (el && zoomRef.current) (d3.select(el) as any).transition().call(zoomRef.current.scaleBy, 1.3); }
    function zoomOut()   { const el = activeEl(); if (el && zoomRef.current) (d3.select(el) as any).transition().call(zoomRef.current.scaleBy, 0.7); }
    function zoomReset() { const el = activeEl(); if (el && zoomRef.current) (d3.select(el) as any).transition().call(zoomRef.current.transform, d3.zoomIdentity); }

    function zoomToNode(nodeId: string, delay = 900) {
        setTimeout(() => {
            const simNode = filteredNodesRef.current.find(n => n.id === nodeId) as any;
            if (!simNode?.x || !simNode?.y || !zoomRef.current) return;
            const el = activeEl();
            if (!el) return;
            const w = (el as HTMLElement).clientWidth;
            const h = (el as HTMLElement).clientHeight;
            (d3.select(el) as any).transition().duration(700).call(
                zoomRef.current.transform,
                d3.zoomIdentity.translate(w / 2 - simNode.x * 1.6, h / 2 - simNode.y * 1.6).scale(1.6),
            );
        }, delay);
    }

    const tour = useTour(zoomToNode, setNodeFilter);

    // URL snapshot read
    useEffect(() => {
        const p = new URLSearchParams(window.location.search);
        if (p.has("nf")) setNodeFilter(p.get("nf") as NodeFilter);
        if (p.has("ef")) setEdgeFilter(p.get("ef") as EdgeFilter);
        if (p.has("df")) setDocFilter(p.get("df")!);
        if (p.has("ld") || p.has("ls") || p.has("le"))
            setLimits({ doc: Number(p.get("ld") || 50), sec: Number(p.get("ls") || 200), entity: Number(p.get("le") || 100) });
        if (p.has("sq")) { setSearchQuery(p.get("sq")!); }
        if (p.has("sn") && data) { const node = data.nodes.find(n => n.id === p.get("sn")!); if (node) setSelectedNode(node); }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // URL snapshot write
    useEffect(() => {
        const p = new URLSearchParams();
        if (nodeFilter !== "全部")    p.set("nf", nodeFilter);
        if (edgeFilter !== "全部关系") p.set("ef", edgeFilter);
        if (searchQuery)              p.set("sq", searchQuery);
        if (docFilter)                p.set("df", docFilter);
        if (limits.doc    !== 50)     p.set("ld", String(limits.doc));
        if (limits.sec    !== 200)    p.set("ls", String(limits.sec));
        if (limits.entity !== 100)    p.set("le", String(limits.entity));
        if (selectedNode)             p.set("sn", selectedNode.id);
        const qs = p.toString();
        window.history.replaceState(null, "", qs ? `${window.location.pathname}?${qs}` : window.location.pathname);
    }, [nodeFilter, edgeFilter, searchQuery, docFilter, limits, selectedNode]);

    // Data loading
    useEffect(() => {
        const params = new URLSearchParams({ limit_doc: String(limits.doc), limit_sec: String(limits.sec), limit_entity: String(limits.entity), doc_id: docFilter });
        fetch(`/api/graph?${params}`).then(r => r.ok ? r.json() : Promise.reject()).then(setData).catch(() => {});
    }, [limits, docFilter]);

    useEffect(() => {
        fetch(`/api/documents?per_page=200`).then(r => r.json())
            .then(d => setDocs((d.data || []).map((doc: any) => ({ doc_id: doc.doc_id, title: doc.title || "" })))).catch(() => {});
    }, []);

    useEffect(() => {
        fetch(`/api/graph/hot-nodes?days=30&top_k=200`).then(r => r.ok ? r.json() : null)
            .then((d: any) => { if (d?.nodes?.length) setHeatMap(new Map(d.nodes.map((n: any) => [n.chunk_id, n.heat_norm]))); }).catch(() => {});
    }, []);

    const handleSearch = useCallback((q: string) => {
        setSearchQuery(q);
        if (!q.trim() || !data) { setHighlightedIds(new Set()); return; }
        const lower = q.toLowerCase();
        const matches = data.nodes.filter(n => (n.name || "").toLowerCase().includes(lower) || (n.id || "").toLowerCase().includes(lower));
        setHighlightedIds(new Set(matches.map(n => n.id)));
        if (matches.length > 0 && svgRef.current && zoomRef.current) {
            const target = matches[0] as any;
            if (target.x !== undefined) {
                const w = svgRef.current.clientWidth, h = svgRef.current.clientHeight;
                d3.select(svgRef.current).transition().duration(500).call(zoomRef.current.transform, d3.zoomIdentity.translate(w / 2 - target.x, h / 2 - target.y));
            }
        }
    }, [data]);

    function exportGraph(format: "json" | "graphml") {
        const nodes = filteredNodesRef.current, edges = filteredEdgesRef.current;
        if (!nodes.length) return;
        if (format === "json") {
            const blob = new Blob([JSON.stringify({ nodes, edges }, null, 2)], { type: "application/json" });
            const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "graph.json"; a.click();
        } else {
            const lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<graphml xmlns="http://graphml.graphdrawing.org/graphml">', '<graph id="G" edgedefault="directed">'];
            nodes.forEach(n => lines.push(`  <node id="${n.id}"><data key="name">${(n.name || "").replace(/&/g,"&amp;")}</data><data key="type">${n.type || ""}</data></node>`));
            edges.forEach((e, i) => { const src = typeof e.source === "object" ? e.source.id : e.source; const tgt = typeof e.target === "object" ? e.target.id : e.target; lines.push(`  <edge id="e${i}" source="${src}" target="${tgt}"><data key="type">${e.type}</data></edge>`); });
            lines.push("</graph>", "</graphml>");
            const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "application/xml" })); a.download = "graph.graphml"; a.click();
        }
    }

    function shareSnapshot() {
        navigator.clipboard.writeText(window.location.href).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
    }

    // Main render effect
    const effectiveData = tour.tourOpen && tour.tourData ? tour.tourData : data;
    useEffect(() => {
        if (!effectiveData || !tooltipRef.current) return;
        const filteredNodes = effectiveData.nodes
            .filter(n => !tour.tourOpen || nodeFilter === "全部" || (n.type || n.label) === nodeFilter)
            .map(n => ({ ...n, x: undefined, y: undefined }));
        const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
        const filteredEdges   = effectiveData.edges
            .filter(e => (edgeFilter === "全部关系" || e.type === edgeFilter) &&
                filteredNodeIds.has(typeof e.source === "string" ? e.source : (e.source as any).id) &&
                filteredNodeIds.has(typeof e.target === "string" ? e.target : (e.target as any).id))
            .map(e => ({ ...e }));
        filteredNodesRef.current = filteredNodes;
        filteredEdgesRef.current = filteredEdges;
        if (pixiDestroyRef.current) { pixiDestroyRef.current(); pixiDestroyRef.current = null; }
        const nc = filteredNodes.length;
        const autoMode: RenderMode = nc > 5000 ? "heatmap" : nc > 1000 ? "webgl" : nc > 500 ? "canvas" : "svg";
        const mode = manualMode ?? autoMode;
        setRenderMode(mode);
        let canceled = false;
        if (mode === "heatmap" && canvasRef.current) {
            zoomRef.current = drawGraphHeatmap({ nodes: filteredNodes, edges: filteredEdges }, canvasRef.current, heatMap, docId => { window.location.href = `/library/${docId}`; });
        } else if (mode === "webgl" && webglRef.current && tooltipRef.current) {
            const wRef = webglRef.current, tRef = tooltipRef.current;
            import("pixi.js").then(PIXI => { if (canceled) return; drawGraphWebGL(PIXI, { nodes: filteredNodes, edges: filteredEdges }, wRef, tRef, setScale, node => setSelectedNode(node), highlightedIds, heatMap).then(({ zoom, destroy }) => { if (canceled) { destroy(); return; } zoomRef.current = zoom; pixiDestroyRef.current = destroy; }).catch(() => {}); }).catch(() => {});
        } else if (mode === "canvas" && canvasRef.current) {
            zoomRef.current = drawGraphCanvas({ nodes: filteredNodes, edges: filteredEdges }, canvasRef.current, tooltipRef.current!, setScale, node => setSelectedNode(node), highlightedIds, heatMap, tour.tourOpen ? tour.tourNodeIds : undefined, tour.tourOpen ? tour.tourCurrentId : undefined);
        } else if (svgRef.current) {
            zoomRef.current = drawGraph({ nodes: filteredNodes, edges: filteredEdges }, svgRef.current, tooltipRef.current!, setScale, node => setSelectedNode(node), highlightedIds, heatMap, tour.tourOpen ? tour.tourNodeIds : undefined, tour.tourOpen ? tour.tourCurrentId : undefined);
        }
        return () => { canceled = true; if (pixiDestroyRef.current) { pixiDestroyRef.current(); pixiDestroyRef.current = null; } };
    }, [effectiveData, nodeFilter, edgeFilter, highlightedIds, heatMap, manualMode, tour.tourNodeIds, tour.tourCurrentId, tour.tourOpen]); // eslint-disable-line react-hooks/exhaustive-deps

    return (
        <div className="w-full h-full bg-gray-950 select-none flex flex-col" onClick={() => { if (showExport) setShowExport(false); }}>
            <GraphToolbar
                nodeFilter={nodeFilter} setNodeFilter={setNodeFilter}
                edgeFilter={edgeFilter} setEdgeFilter={setEdgeFilter}
                searchQuery={searchQuery} handleSearch={handleSearch}
                docFilter={docFilter} setDocFilter={setDocFilter} docs={docs}
                tourOpen={tour.tourOpen} onTourToggle={() => { tour.setTourOpen(v => !v); if (tour.tourRunning) tour.stopTour(); }}
                showLimits={showLimits} setShowLimits={setShowLimits}
                showLegend={showLegend} setShowLegend={setShowLegend}
                showExport={showExport} setShowExport={setShowExport}
                copied={copied} shareSnapshot={shareSnapshot} exportGraph={exportGraph}
                renderMode={renderMode} manualMode={manualMode} setManualMode={setManualMode}
            />

            <div className="flex-1 flex flex-col overflow-hidden min-h-0">
                <div className="flex-1 flex overflow-hidden min-h-0">
                    <div className="relative flex-1 overflow-hidden">
                        <svg    ref={svgRef}    className={`w-full h-full${renderMode === "svg"                              ? "" : " hidden"}`} />
                        <canvas ref={canvasRef} className={`w-full h-full${renderMode === "canvas" || renderMode === "heatmap" ? "" : " hidden"}`} />
                        <canvas ref={webglRef}  className={`w-full h-full${renderMode === "webgl"                            ? "" : " hidden"}`} />

                        {renderMode !== "svg" && (
                            <div className="absolute top-3 left-3 px-2 py-1 bg-gray-900/80 border border-indigo-700/40 rounded-lg text-xs text-indigo-400 pointer-events-none z-10">
                                {renderMode === "webgl"   && `WebGL 模式 · ${filteredNodesRef.current.length} 节点`}
                                {renderMode === "canvas"  && `Canvas 模式 · ${filteredNodesRef.current.length} 节点`}
                                {renderMode === "heatmap" && `热力图模式 · ${filteredNodesRef.current.length} 节点（按文档聚类）`}
                            </div>
                        )}

                        {showLimits && (
                            <div className="absolute top-3 left-3 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 space-y-3 w-56 z-10 shadow-xl">
                                <div className="text-xs text-gray-400 font-medium">节点数量限制</div>
                                {([
                                    { key: "doc",    label: "Document", min: 10,  max: 200 },
                                    { key: "sec",    label: "Section",  min: 50,  max: 500 },
                                    { key: "entity", label: "Entity",   min: 20,  max: 200 },
                                ] as { key: keyof Limits; label: string; min: number; max: number }[]).map(({ key, label, min, max }) => (
                                    <div key={key} className="flex items-center gap-2">
                                        <span className="text-xs text-gray-400 w-16">{label}</span>
                                        <input type="range" min={min} max={max} step={10} value={limits[key]}
                                            onChange={e => setLimits(prev => ({ ...prev, [key]: Number(e.target.value) }))}
                                            className="flex-1 h-1 accent-indigo-500" />
                                        <span className="text-xs text-gray-500 w-8 text-right">{limits[key]}</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        {showLegend && (
                            <div className="absolute top-3 right-3 bg-gray-900 border border-gray-700 rounded-xl px-3 py-2.5 z-10 shadow-xl">
                                <div className="text-xs text-gray-500 mb-2">节点类型</div>
                                <div className="flex flex-col gap-1.5">
                                    {Object.entries(NODE_COLOR).map(([k, c]) => (
                                        <div key={k} className="flex items-center gap-2">
                                            <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: c }} />
                                            <span className="text-xs text-gray-400">{k}</span>
                                        </div>
                                    ))}
                                </div>
                                {heatMap.size > 0 && (
                                    <div className="mt-3 pt-2.5 border-t border-gray-800">
                                        <div className="text-xs text-gray-500 mb-2">查询热力</div>
                                        <div className="flex items-center gap-2">
                                            <div className="flex gap-0.5">
                                                {[0.2, 0.5, 1].map(v => (
                                                    <div key={v} className="rounded-full border border-amber-500/60"
                                                        style={{ width: Math.round(8 + v * 12), height: Math.round(8 + v * 12), backgroundColor: `rgba(245,158,11,${0.15 + v * 0.25})` }} />
                                                ))}
                                            </div>
                                            <span className="text-xs text-gray-400">低 → 高</span>
                                        </div>
                                        <div className="text-xs text-gray-600 mt-1">{heatMap.size} 个热点章节</div>
                                    </div>
                                )}
                            </div>
                        )}

                        {tour.tourOpen && tour.tourRunning && tour.tourIdx >= 0 && (
                            <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 bg-gray-900/90 border border-amber-500/40 rounded-full px-4 py-1.5 flex items-center gap-2 backdrop-blur-sm">
                                <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shrink-0" />
                                <span className="text-xs text-amber-300 font-medium">漫游中 · 第 {tour.tourIdx + 1}/{tour.tourTotal} 站</span>
                            </div>
                        )}

                        <div className="absolute bottom-4 right-4 flex items-center gap-2">
                            <span className="text-xs text-gray-600 mr-1">拖拽平移 · 滚轮缩放</span>
                            <button onClick={zoomOut} disabled={scale <= MIN_SCALE} className="w-7 h-7 rounded bg-gray-800 text-white text-sm hover:bg-gray-700 disabled:opacity-30 flex items-center justify-center">−</button>
                            <button onClick={() => { zoomReset(); setNodeFilter("全部"); setEdgeFilter("全部关系"); }} className="px-2 h-7 rounded bg-gray-800 text-xs text-gray-300 hover:bg-gray-700">重置</button>
                            <button onClick={zoomIn}  disabled={scale >= MAX_SCALE}  className="w-7 h-7 rounded bg-gray-800 text-white text-sm hover:bg-gray-700 disabled:opacity-30 flex items-center justify-center">+</button>
                        </div>

                        <div ref={tooltipRef} className="fixed hidden px-2 py-1 bg-gray-800 text-white text-xs rounded pointer-events-none border border-gray-700 max-w-xs" />
                    </div>

                    {selectedNode && <NodeDetailSidebar node={selectedNode} onClose={() => setSelectedNode(null)} />}
                </div>

                {tour.tourOpen && (
                    <TourPanel
                        tourTopic={tour.tourTopic} setTourTopic={tour.setTourTopic}
                        tourRunning={tour.tourRunning} tourStops={tour.tourStops}
                        tourIdx={tour.tourIdx} tourTotal={tour.tourTotal}
                        tourText={tour.tourText} tourStreaming={tour.tourStreaming}
                        hasPrev={tour.hasPrev} hasNext={tour.hasNext}
                        onStart={tour.startTour} onStop={tour.stopTour}
                        onNavigate={tour.navigateTour}
                        onClose={() => { tour.setTourOpen(false); if (tour.tourRunning) tour.stopTour(); }}
                    />
                )}
            </div>
        </div>
    );
}
