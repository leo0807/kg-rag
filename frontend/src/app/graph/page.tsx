"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { Settings, Search, Download, X, Layers, Share2, Check } from "lucide-react";

interface GraphNode {
    id: string;
    label: string;
    name: string;
    type?: string;
    doc_id?: string;
    description?: string;
    path?: string;
    x?: number;
    y?: number;
}

interface GraphEdge {
    source: string | GraphNode;
    target: string | GraphNode;
    type: string;
}

interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

interface SimNode extends GraphNode {
    fx?: number | null;
    fy?: number | null;
}

const MIN_SCALE = 0.1;
const MAX_SCALE = 4;

const NODE_COLOR: Record<string, string> = {
    Document:   "#6366f1",
    Section:    "#f59e0b",
    Image:      "#ec4899",
    Tool:       "#10b981",
    Material:   "#f97316",
    Process:    "#a78bfa",
    Constraint: "#ef4444",
};

// 工具栏中显示的中文缩写
const NODE_SHORT: Record<string, string> = {
    "全部":       "全部",
    Document:   "文档",
    Section:    "章节",
    Image:      "图片",
    Tool:       "工具",
    Material:   "材料",
    Process:    "工序",
    Constraint: "约束",
};

const EDGE_COLOR: Record<string, string> = {
    HAS_SECTION:       "#4f46e5",
    REFERENCES:        "#059669",
    HAS_SUBSECTION:    "#d97706",
    NEXT_SECTION:      "#6b7280",
    HAS_IMAGE:         "#ec4899",
    REQUIRES_TOOL:     "#10b981",
    USES_MATERIAL:     "#f97316",
    INVOLVES_PROCESS:  "#a78bfa",
    HAS_CONSTRAINT:    "#ef4444",
    ALTERNATIVE_TO:    "#fb923c",
    COMPATIBLE_WITH:   "#34d399",
    MENTIONS_TOOL:     "#6ee7b7",
    SUPERSEDES:        "#818cf8",
    SIMILAR_TO:        "#94a3b8",
    CHANGED_TO:        "#fbbf24",
};

const NODE_TYPES = ["全部","Document","Section","Image","Tool","Material","Process","Constraint"] as const;
const EDGE_TYPES = [
    "全部关系","HAS_SECTION","REFERENCES","HAS_SUBSECTION","HAS_IMAGE",
    "REQUIRES_TOOL","USES_MATERIAL","INVOLVES_PROCESS","HAS_CONSTRAINT",
    "ALTERNATIVE_TO","COMPATIBLE_WITH","SUPERSEDES","SIMILAR_TO",
] as const;

type NodeFilter = typeof NODE_TYPES[number];
type EdgeFilter = typeof EDGE_TYPES[number];
interface Limits { doc: number; sec: number; entity: number; }

function nodeRadius(d: SimNode): number {
    const t = d.type || d.label;
    if (t === "Document")   return 36;
    if (t === "Image")      return 18;
    if (t === "Constraint") return 14;
    if (t === "Tool" || t === "Material" || t === "Process") return 16;
    return 22;
}

function drawGraph(
    data: GraphData,
    svgEl: SVGSVGElement,
    tooltipEl: HTMLDivElement,
    onScaleChange: (s: number) => void,
    onNodeClick: (node: GraphNode) => void,
    highlightedIds: Set<string>,
): d3.ZoomBehavior<SVGSVGElement, unknown> {
    const width  = svgEl.clientWidth;
    const height = svgEl.clientHeight;

    d3.select(svgEl).selectAll("*").remove();

    const svg       = d3.select(svgEl);
    const container = svg.append("g");

    const zoom = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([MIN_SCALE, MAX_SCALE])
        .on("zoom", event => {
            container.attr("transform", event.transform);
            onScaleChange(event.transform.k);
        });

    svg.call(zoom);
    svg.call(zoom.transform, d3.zoomIdentity);

    svg.style("cursor", "grab")
        .on("mousedown.cursor", () => svg.style("cursor", "grabbing"))
        .on("mouseup.cursor",   () => svg.style("cursor", "grab"));

    const nodeCount      = data.nodes.length;
    const chargeStrength = nodeCount > 50 ? -150 : -500;
    const linkDistance   = nodeCount > 50 ? 60   : 140;

    (data.nodes as SimNode[]).forEach(node => {
        if (node.x === undefined) {
            node.x = width  / 2 + (Math.random() - 0.5) * 100;
            node.y = height / 2 + (Math.random() - 0.5) * 100;
        }
    });

    const simulation = d3.forceSimulation(data.nodes as SimNode[])
        .force("link",    d3.forceLink(data.edges).id((d: any) => d.id).distance(linkDistance))
        .force("charge",  d3.forceManyBody().strength(chargeStrength))
        .force("center",  d3.forceCenter(width / 2, height / 2))
        .force("collide", d3.forceCollide<SimNode>().radius(d => nodeRadius(d) + 8).strength(0.8))
        .alphaDecay(0.03)
        .velocityDecay(0.4);

    const link = container.append("g")
        .selectAll("line")
        .data(data.edges)
        .join("line")
        .attr("stroke",         (d: any) => EDGE_COLOR[d.type] ?? "#374151")
        .attr("stroke-width",   (d: any) => d.type === "REFERENCES" ? 2 : 1.5)
        .attr("stroke-opacity", 0.6)
        .attr("stroke-dasharray", (d: any) =>
            d.type === "HAS_IMAGE" || d.type === "MENTIONS_TOOL" ? "4 2" : null
        );

    const node = container.append("g")
        .selectAll("g")
        .data(data.nodes as SimNode[])
        .join("g")
        .attr("cursor", "pointer")
        .call(
            d3.drag<any, SimNode>()
                .filter(event => event.button === 0)
                .on("start", (event, d) => {
                    event.sourceEvent.stopPropagation();
                    if (!event.active) simulation.alphaTarget(0.3).restart();
                    d.fx = d.x; d.fy = d.y;
                })
                .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
                .on("end",  (event, d) => {
                    if (!event.active) simulation.alphaTarget(0);
                    d.fx = null; d.fy = null;
                })
        );

    node.on("click", (event: MouseEvent, d: SimNode) => {
        if (event.defaultPrevented) return;
        onNodeClick(d as GraphNode);
    });

    node.filter(d => highlightedIds.has(d.id))
        .append("circle")
        .attr("r",              d => nodeRadius(d) + 6)
        .attr("fill",           "none")
        .attr("stroke",         "#f97316")
        .attr("stroke-width",   2.5)
        .attr("stroke-opacity", 0.9);

    node.append("circle")
        .attr("r",    d => nodeRadius(d))
        .attr("fill", d => NODE_COLOR[d.type || d.label] ?? "#6b7280")
        .attr("stroke",       d => highlightedIds.has(d.id) ? "#f97316" : "none")
        .attr("stroke-width", 2);

    node
        .on("mouseover", (event: MouseEvent, d) => {
            const t    = d3.select(tooltipEl);
            const desc = (d as any).description;
            t.classed("hidden", false)
                .style("left", (event.clientX + 12) + "px")
                .style("top",  (event.clientY - 8)  + "px")
                .html(desc
                    ? `<div class="font-medium">${d.name}</div><div class="text-gray-400 mt-1 max-w-xs">${desc.slice(0, 80)}…</div>`
                    : d.name
                );
        })
        .on("mousemove", (event: MouseEvent) => {
            d3.select(tooltipEl)
                .style("left", (event.clientX + 12) + "px")
                .style("top",  (event.clientY - 8)  + "px");
        })
        .on("mouseout", () => { d3.select(tooltipEl).classed("hidden", true); });

    node.append("text")
        .text(d => {
            const name = d.name || d.label || "";
            return name.length > 6 ? name.slice(0, 6) + "…" : name;
        })
        .attr("font-size",         d => (d.type || d.label) === "Document" ? 12 : 10)
        .attr("fill",              "#fff")
        .attr("text-anchor",       "middle")
        .attr("dominant-baseline", "central")
        .attr("pointer-events",    "none");

    simulation.on("tick", () => {
        link
            .attr("x1", (d: any) => d.source.x)
            .attr("y1", (d: any) => d.source.y)
            .attr("x2", (d: any) => d.target.x)
            .attr("y2", (d: any) => d.target.y);
        node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });

    return zoom;
}

// ── 节点详情侧边栏 ────────────────────────────────────────────────────────────
function NodeDetailSidebar({ node, onClose }: { node: GraphNode; onClose: () => void }) {
    const type    = node.type || node.label;
    const color   = NODE_COLOR[type] ?? "#6b7280";
    const imgPath = node.path
        ? `http://localhost:8000/${node.path.replace(/^.*?(uploads\/)/, "uploads/")}`
        : null;

    return (
        <div className="w-72 shrink-0 bg-gray-900 border-l border-gray-700 flex flex-col overflow-auto">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
                <span
                    className="text-xs px-2 py-0.5 rounded-full font-medium"
                    style={{ backgroundColor: color + "33", color }}
                >
                    {type}
                </span>
                <button onClick={onClose} className="p-1 rounded hover:bg-gray-800 text-gray-500 hover:text-white transition-colors">
                    <X size={14} />
                </button>
            </div>

            <div className="px-4 py-3 border-b border-gray-800">
                <div className="text-sm font-semibold text-white leading-snug">{node.name || node.id}</div>
                {node.doc_id && (
                    <div className="text-xs text-gray-500 font-mono mt-1">{node.doc_id}</div>
                )}
            </div>

            {imgPath && (
                <div className="px-4 py-3 border-b border-gray-800 bg-gray-950">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                        src={imgPath}
                        alt={node.name}
                        className="max-h-48 w-full object-contain rounded-lg"
                        onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                </div>
            )}

            {node.description && (
                <div className="px-4 py-3 border-b border-gray-800">
                    <div className="text-xs text-gray-500 mb-1">VLM 分析</div>
                    <p className="text-xs text-gray-300 leading-relaxed">{node.description}</p>
                </div>
            )}

            <div className="px-4 py-3 space-y-2">
                {Object.entries(node)
                    .filter(([k]) => !["id","name","label","type","x","y","fx","fy","description","path"].includes(k))
                    .map(([k, v]) => v != null && String(v) !== "" && (
                        <div key={k} className="flex gap-2">
                            <span className="text-xs text-gray-600 w-20 shrink-0">{k}</span>
                            <span className="text-xs text-gray-300 break-all">{String(v)}</span>
                        </div>
                    ))}
            </div>

            {type === "Document" && (
                <div className="px-4 pb-4 mt-auto">
                    <a href={`/library/${node.doc_id || node.id}`}
                        className="block w-full text-center px-3 py-2 bg-indigo-600 hover:bg-indigo-700
                                   text-white text-xs rounded-lg transition-colors">
                        查看文档
                    </a>
                </div>
            )}
        </div>
    );
}

// ── 主页面 ────────────────────────────────────────────────────────────────────
export default function GraphPage() {
    const svgRef     = useRef<SVGSVGElement>(null);
    const tooltipRef = useRef<HTMLDivElement>(null);
    const zoomRef    = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);

    const filteredNodesRef  = useRef<GraphNode[]>([]);
    const filteredEdgesRef  = useRef<GraphEdge[]>([]);
    const pendingSearchRef  = useRef("");          // 待恢复的搜索词（URL init）
    const pendingNodeIdRef  = useRef("");          // 待恢复的选中节点 ID（URL init）

    const [data,           setData]           = useState<GraphData | null>(null);
    const [scale,          setScale]          = useState(1);
    const [nodeFilter,     setNodeFilter]     = useState<NodeFilter>("全部");
    const [edgeFilter,     setEdgeFilter]     = useState<EdgeFilter>("全部关系");
    const [selectedNode,   setSelectedNode]   = useState<GraphNode | null>(null);
    const [searchQuery,    setSearchQuery]    = useState("");
    const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());
    const [docFilter,      setDocFilter]      = useState("");
    const [docs,           setDocs]           = useState<{doc_id: string; title: string}[]>([]);
    const [limits,         setLimits]         = useState<Limits>({ doc: 50, sec: 200, entity: 100 });
    const [showLimits,     setShowLimits]     = useState(false);
    const [showLegend,     setShowLegend]     = useState(false);
    const [showExport,     setShowExport]     = useState(false);
    const [copied,         setCopied]         = useState(false);

    function zoomIn()    { if (svgRef.current && zoomRef.current) d3.select(svgRef.current).transition().call(zoomRef.current.scaleBy, 1.3); }
    function zoomOut()   { if (svgRef.current && zoomRef.current) d3.select(svgRef.current).transition().call(zoomRef.current.scaleBy, 0.7); }
    function zoomReset() { if (svgRef.current && zoomRef.current) d3.select(svgRef.current).transition().call(zoomRef.current.transform, d3.zoomIdentity); }

    // ── URL 快照：初始化（从 URL 恢复状态，仅运行一次）────────────────────────
    useEffect(() => {
        const p = new URLSearchParams(window.location.search);
        if (p.has("nf")) setNodeFilter(p.get("nf") as NodeFilter);
        if (p.has("ef")) setEdgeFilter(p.get("ef") as EdgeFilter);
        if (p.has("df")) setDocFilter(p.get("df")!);
        if (p.has("ld") || p.has("ls") || p.has("le")) {
            setLimits({
                doc:    Number(p.get("ld") || 50),
                sec:    Number(p.get("ls") || 200),
                entity: Number(p.get("le") || 100),
            });
        }
        if (p.has("sq")) {
            const sq = p.get("sq")!;
            setSearchQuery(sq);
            pendingSearchRef.current = sq;
        }
        if (p.has("sn")) {
            pendingNodeIdRef.current = p.get("sn")!;
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // ── URL 快照：同步（状态变更时写回 URL）──────────────────────────────────
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
        const qs     = p.toString();
        const newUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
        window.history.replaceState(null, "", newUrl);
    }, [nodeFilter, edgeFilter, searchQuery, docFilter, limits, selectedNode]);

    // ── 复制当前 URL 到剪贴板 ─────────────────────────────────────────────────
    function shareSnapshot() {
        navigator.clipboard.writeText(window.location.href).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    }

    useEffect(() => {
        const params = new URLSearchParams({
            limit_doc:    String(limits.doc),
            limit_sec:    String(limits.sec),
            limit_entity: String(limits.entity),
            doc_id:       docFilter,
        });
        fetch(`/api/graph?${params}`).then(r => r.json()).then(setData);
    }, [limits, docFilter]);

    useEffect(() => {
        fetch("/api/documents?per_page=200")
            .then(r => r.json())
            .then(d => setDocs((d.data || []).map((doc: any) => ({ doc_id: doc.doc_id, title: doc.title || "" }))))
            .catch(() => {});
    }, []);

    const handleSearch = useCallback((q: string) => {
        setSearchQuery(q);
        if (!q.trim() || !data) { setHighlightedIds(new Set()); return; }
        const lower   = q.toLowerCase();
        const matches = data.nodes.filter(n =>
            (n.name || "").toLowerCase().includes(lower) ||
            (n.id   || "").toLowerCase().includes(lower)
        );
        setHighlightedIds(new Set(matches.map(n => n.id)));

        if (matches.length > 0 && svgRef.current && zoomRef.current) {
            const target = matches[0] as SimNode;
            if (target.x !== undefined && target.y !== undefined) {
                const w = svgRef.current.clientWidth;
                const h = svgRef.current.clientHeight;
                d3.select(svgRef.current).transition().duration(500).call(
                    zoomRef.current.transform,
                    d3.zoomIdentity.translate(w / 2 - target.x, h / 2 - target.y)
                );
            }
        }
    }, [data]);

    function exportGraph(format: "json" | "graphml") {
        const nodes = filteredNodesRef.current;
        const edges = filteredEdgesRef.current;
        if (!nodes.length) return;

        if (format === "json") {
            const blob = new Blob([JSON.stringify({ nodes, edges }, null, 2)], { type: "application/json" });
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement("a"); a.href = url; a.download = "graph.json"; a.click();
        } else {
            const lines = [
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<graphml xmlns="http://graphml.graphdrawing.org/graphml">',
                '<graph id="G" edgedefault="directed">',
            ];
            nodes.forEach(n => lines.push(
                `  <node id="${n.id}"><data key="name">${(n.name || "").replace(/&/g,"&amp;")}</data><data key="type">${n.type || ""}</data></node>`
            ));
            edges.forEach((e, i) => {
                const src = typeof e.source === "object" ? (e.source as any).id : e.source;
                const tgt = typeof e.target === "object" ? (e.target as any).id : e.target;
                lines.push(`  <edge id="e${i}" source="${src}" target="${tgt}"><data key="type">${e.type}</data></edge>`);
            });
            lines.push("</graph>", "</graphml>");
            const blob = new Blob([lines.join("\n")], { type: "application/xml" });
            const url  = URL.createObjectURL(blob);
            const a    = document.createElement("a"); a.href = url; a.download = "graph.graphml"; a.click();
        }
    }

    // ── 数据加载后恢复搜索高亮与选中节点 ──────────────────────────────────────
    useEffect(() => {
        if (!data) return;
        if (pendingSearchRef.current) {
            handleSearch(pendingSearchRef.current);
            pendingSearchRef.current = "";
        }
        if (pendingNodeIdRef.current) {
            const node = data.nodes.find(n => n.id === pendingNodeIdRef.current);
            if (node) setSelectedNode(node);
            pendingNodeIdRef.current = "";
        }
    }, [data, handleSearch]);

    useEffect(() => {
        if (!data || !svgRef.current || !tooltipRef.current) return;

        const filteredNodes = data.nodes
            .filter(n => nodeFilter === "全部" || (n.type || n.label) === nodeFilter)
            .map(n => ({ ...n, x: undefined, y: undefined }));

        const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
        const filteredEdges   = data.edges
            .filter(e =>
                (edgeFilter === "全部关系" || e.type === edgeFilter) &&
                filteredNodeIds.has(typeof e.source === "string" ? e.source : (e.source as any).id) &&
                filteredNodeIds.has(typeof e.target === "string" ? e.target : (e.target as any).id)
            )
            .map(e => ({ ...e }));

        filteredNodesRef.current = filteredNodes;
        filteredEdgesRef.current = filteredEdges;

        zoomRef.current = drawGraph(
            { nodes: filteredNodes, edges: filteredEdges },
            svgRef.current,
            tooltipRef.current,
            setScale,
            node => setSelectedNode(node),
            highlightedIds,
        );
    }, [data, nodeFilter, edgeFilter, highlightedIds]);

    return (
        <div
            className="w-full h-full bg-gray-950 select-none flex flex-col"
            onClick={() => { if (showExport) setShowExport(false); }}
        >
            {/* ── 紧凑工具栏 (44px) ─────────────────────────────────────────── */}
            <div className="shrink-0 flex items-center gap-1.5 px-3 h-11 bg-gray-900 border-b border-gray-800 z-20">

                {/* 节点类型过滤 — 彩色圆点 chip */}
                <div className="flex items-center gap-0.5">
                    {NODE_TYPES.map(type => (
                        <button
                            key={type}
                            onClick={() => setNodeFilter(type)}
                            title={type}
                            className={`flex items-center gap-1 px-2 h-7 rounded text-xs font-medium transition-colors whitespace-nowrap ${
                                nodeFilter === type
                                    ? "bg-indigo-600 text-white"
                                    : "text-gray-400 hover:text-white hover:bg-gray-800"
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

                <div className="w-px h-5 bg-gray-700 mx-0.5 shrink-0" />

                {/* 边类型过滤 — 下拉选择 */}
                <select
                    value={edgeFilter}
                    onChange={e => setEdgeFilter(e.target.value as EdgeFilter)}
                    className="h-7 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300
                               outline-none focus:border-indigo-500 max-w-[138px]"
                >
                    {EDGE_TYPES.map(t => (
                        <option key={t} value={t}>{t}</option>
                    ))}
                </select>

                <div className="flex-1" />

                {/* 搜索框 */}
                <div className="relative">
                    <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                    <input
                        value={searchQuery}
                        onChange={e => handleSearch(e.target.value)}
                        placeholder="搜索节点…"
                        className="pl-6 pr-2 h-7 w-28 bg-gray-800 border border-gray-700 rounded
                                   text-xs text-gray-200 outline-none focus:border-indigo-500"
                    />
                </div>

                {/* 文档过滤 */}
                <select
                    value={docFilter}
                    onChange={e => setDocFilter(e.target.value)}
                    className="h-7 px-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-400
                               outline-none focus:border-indigo-500 max-w-[110px]"
                >
                    <option value="">全部文档</option>
                    {docs.map(d => (
                        <option key={d.doc_id} value={d.doc_id}>{d.doc_id}</option>
                    ))}
                </select>

                <div className="w-px h-5 bg-gray-700 mx-0.5 shrink-0" />

                {/* 节点数量设置 */}
                <button
                    onClick={() => { setShowLimits(v => !v); setShowLegend(false); }}
                    className={`p-1.5 rounded transition-colors ${
                        showLimits ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"
                    }`}
                    title="节点数量"
                >
                    <Settings size={14} />
                </button>

                {/* 图例 */}
                <button
                    onClick={() => { setShowLegend(v => !v); setShowLimits(false); }}
                    className={`p-1.5 rounded transition-colors ${
                        showLegend ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"
                    }`}
                    title="图例"
                >
                    <Layers size={14} />
                </button>

                {/* 分享快照 */}
                <button
                    onClick={shareSnapshot}
                    className={`p-1.5 rounded transition-colors ${
                        copied ? "bg-emerald-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"
                    }`}
                    title="复制分享链接"
                >
                    {copied ? <Check size={14} /> : <Share2 size={14} />}
                </button>

                {/* 导出下拉 */}
                <div className="relative" onClick={e => e.stopPropagation()}>
                    <button
                        onClick={() => setShowExport(v => !v)}
                        className={`p-1.5 rounded transition-colors ${
                            showExport ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-white hover:bg-gray-800"
                        }`}
                        title="导出"
                    >
                        <Download size={14} />
                    </button>
                    {showExport && (
                        <div className="absolute right-0 top-full mt-1 bg-gray-900 border border-gray-700
                                        rounded-lg py-1 w-28 shadow-xl z-30">
                            <button
                                onClick={() => { exportGraph("json"); setShowExport(false); }}
                                className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800"
                            >
                                导出 JSON
                            </button>
                            <button
                                onClick={() => { exportGraph("graphml"); setShowExport(false); }}
                                className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800"
                            >
                                导出 GraphML
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* ── 图谱主区域 ────────────────────────────────────────────────── */}
            <div className="flex-1 flex overflow-hidden">
                <div className="relative flex-1 overflow-hidden">
                    <svg ref={svgRef} className="w-full h-full" />

                    {/* 浮动：节点数量面板 */}
                    {showLimits && (
                        <div className="absolute top-3 left-3 bg-gray-900 border border-gray-700 rounded-xl
                                        px-4 py-3 space-y-3 w-56 z-10 shadow-xl">
                            <div className="text-xs text-gray-400 font-medium">节点数量限制</div>
                            {([
                                { key: "doc",    label: "Document", min: 10,  max: 200 },
                                { key: "sec",    label: "Section",  min: 50,  max: 500 },
                                { key: "entity", label: "Entity",   min: 20,  max: 200 },
                            ] as { key: keyof Limits; label: string; min: number; max: number }[]).map(({ key, label, min, max }) => (
                                <div key={key} className="flex items-center gap-2">
                                    <span className="text-xs text-gray-400 w-16">{label}</span>
                                    <input
                                        type="range"
                                        min={min} max={max} step={10}
                                        value={limits[key]}
                                        onChange={e => setLimits(prev => ({ ...prev, [key]: Number(e.target.value) }))}
                                        className="flex-1 h-1 accent-indigo-500"
                                    />
                                    <span className="text-xs text-gray-500 w-8 text-right">{limits[key]}</span>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* 浮动：图例面板 */}
                    {showLegend && (
                        <div className="absolute top-3 right-3 bg-gray-900 border border-gray-700 rounded-xl
                                        px-3 py-2.5 z-10 shadow-xl">
                            <div className="text-xs text-gray-500 mb-2">节点类型</div>
                            <div className="flex flex-col gap-1.5">
                                {Object.entries(NODE_COLOR).map(([k, c]) => (
                                    <div key={k} className="flex items-center gap-2">
                                        <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: c }} />
                                        <span className="text-xs text-gray-400">{k}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* 缩放控制 */}
                    <div className="absolute bottom-4 right-4 flex items-center gap-2">
                        <span className="text-xs text-gray-600 mr-1">拖拽平移 · 滚轮缩放</span>
                        <button
                            onClick={zoomOut}
                            disabled={scale <= MIN_SCALE}
                            className="w-7 h-7 rounded bg-gray-800 text-white text-sm hover:bg-gray-700
                                       disabled:opacity-30 flex items-center justify-center"
                        >−</button>
                        <button
                            onClick={() => { zoomReset(); setNodeFilter("全部"); setEdgeFilter("全部关系"); }}
                            className="px-2 h-7 rounded bg-gray-800 text-xs text-gray-300 hover:bg-gray-700"
                        >重置</button>
                        <button
                            onClick={zoomIn}
                            disabled={scale >= MAX_SCALE}
                            className="w-7 h-7 rounded bg-gray-800 text-white text-sm hover:bg-gray-700
                                       disabled:opacity-30 flex items-center justify-center"
                        >+</button>
                    </div>

                    {/* Tooltip */}
                    <div
                        ref={tooltipRef}
                        className="fixed hidden px-2 py-1 bg-gray-800 text-white text-xs
                                   rounded pointer-events-none border border-gray-700 max-w-xs"
                    />
                </div>

                {/* 节点详情侧边栏 */}
                {selectedNode && (
                    <NodeDetailSidebar
                        node={selectedNode}
                        onClose={() => setSelectedNode(null)}
                    />
                )}
            </div>
        </div>
    );
}
