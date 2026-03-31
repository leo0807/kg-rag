"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { SourceSection } from "./types";

// ── 颜色配置（与主图谱页保持一致）─────────────────────────────────────────
const NODE_COLOR: Record<string, string> = {
    Document:   "#6366f1",
    Section:    "#f59e0b",
    Tool:       "#10b981",
    Material:   "#f97316",
    Process:    "#a78bfa",
    Constraint: "#ef4444",
};

const EDGE_COLOR: Record<string, string> = {
    HAS_SECTION:       "#4f46e5",
    HAS_SUBSECTION:    "#d97706",
    NEXT_SECTION:      "#4b5563",
    REQUIRES_TOOL:     "#10b981",
    USES_MATERIAL:     "#f97316",
    INVOLVES_PROCESS:  "#a78bfa",
    HAS_CONSTRAINT:    "#ef4444",
};

// 来源节点：排名 1~5 对应颜色，第 6 及之后统一用暗色
const RANK_COLORS = [
    "#fbbf24", // rank 1 — 金
    "#34d399", // rank 2 — 绿
    "#60a5fa", // rank 3 — 蓝
    "#f472b6", // rank 4 — 粉
    "#a78bfa", // rank 5 — 紫
];
function rankColor(rank: number) {
    return RANK_COLORS[rank - 1] ?? "#6b7280";
}

interface GraphNode {
    id: string; name: string; type: string;
    doc_id?: string; rank: number;
    x?: number; y?: number; fx?: number | null; fy?: number | null;
}
interface GraphEdge { source: string; target: string; type: string; }

function drawSourceGraph(
    svgEl: SVGSVGElement,
    data: { nodes: GraphNode[]; edges: GraphEdge[] },
) {
    const W = svgEl.clientWidth;
    const H = svgEl.clientHeight;
    d3.select(svgEl).selectAll("*").remove();

    const svg       = d3.select(svgEl);
    const container = svg.append("g");

    // 允许平移/缩放
    const zoom = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 4])
        .on("zoom", e => container.attr("transform", e.transform));
    svg.call(zoom).style("cursor", "grab")
        .on("mousedown.c", () => svg.style("cursor", "grabbing"))
        .on("mouseup.c",   () => svg.style("cursor", "grab"));

    const r = (d: GraphNode) => {
        if (d.type === "Document")   return 20;
        if (d.rank > 0)              return 18;
        if (d.type === "Constraint") return 10;
        return 12;
    };

    (data.nodes as GraphNode[]).forEach(n => {
        if (!n.x) { n.x = W / 2 + (Math.random() - 0.5) * 80; }
        if (!n.y) { n.y = H / 2 + (Math.random() - 0.5) * 80; }
    });

    const sim = d3.forceSimulation(data.nodes as GraphNode[])
        .force("link",    d3.forceLink(data.edges).id((d: any) => d.id).distance(80))
        .force("charge",  d3.forceManyBody().strength(-200))
        .force("center",  d3.forceCenter(W / 2, H / 2))
        .force("collide", d3.forceCollide<GraphNode>().radius(d => r(d) + 6).strength(0.9))
        .alphaDecay(0.03)
        .velocityDecay(0.45);

    // 边
    const link = container.append("g")
        .selectAll("line").data(data.edges).join("line")
        .attr("stroke",         (d: any) => EDGE_COLOR[d.type] ?? "#374151")
        .attr("stroke-width",   1.5)
        .attr("stroke-opacity", 0.5)
        .attr("stroke-dasharray", (d: any) =>
            d.type === "NEXT_SECTION" || d.type === "HAS_CONSTRAINT" ? "4 2" : null
        );

    // 边标签（关系类型，仅主要关系）
    const SHOW_LABEL = new Set(["REQUIRES_TOOL", "USES_MATERIAL", "INVOLVES_PROCESS", "HAS_CONSTRAINT"]);
    const linkLabel = container.append("g")
        .selectAll("text").data(data.edges.filter(e => SHOW_LABEL.has(e.type))).join("text")
        .attr("font-size", 8)
        .attr("fill", (d: any) => EDGE_COLOR[d.type] ?? "#9ca3af")
        .attr("text-anchor", "middle")
        .attr("pointer-events", "none")
        .attr("opacity", 0.75)
        .text((d: any) => d.type.replace(/_/g, " "));

    // 节点
    const node = container.append("g")
        .selectAll("g").data(data.nodes as GraphNode[]).join("g")
        .attr("cursor", "grab")
        .call(
            d3.drag<any, GraphNode>()
                .filter(e => e.button === 0)
                .on("start", (e, d) => {
                    e.sourceEvent.stopPropagation();
                    if (!e.active) sim.alphaTarget(0.3).restart();
                    d.fx = d.x; d.fy = d.y;
                })
                .on("drag",  (e, d) => { d.fx = e.x; d.fy = e.y; })
                .on("end",   (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
        );

    // 来源节点加发光外圈
    node.filter((d: GraphNode) => d.rank > 0).append("circle")
        .attr("r", d => r(d) + 4)
        .attr("fill", "none")
        .attr("stroke", d => rankColor(d.rank))
        .attr("stroke-width", 1.5)
        .attr("stroke-opacity", 0.4);

    // 主体圆
    node.append("circle")
        .attr("r", d => r(d))
        .attr("fill", d => {
            if (d.rank > 0) return rankColor(d.rank);
            return NODE_COLOR[d.type] ?? "#6b7280";
        })
        .attr("fill-opacity", d => d.rank > 0 ? 1 : 0.7);

    // 文字
    node.append("text")
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "central")
        .attr("pointer-events", "none")
        .each(function (d: GraphNode) {
            const el = d3.select(this);
            if (d.rank > 0) {
                // 排名来源节点：上方显示排名数字，下方显示截断名称
                el.append("tspan")
                    .attr("x", 0).attr("dy", "-0.35em")
                    .attr("font-size", 11).attr("font-weight", "bold")
                    .attr("fill", "#000")
                    .text(`#${d.rank}`);
                el.append("tspan")
                    .attr("x", 0).attr("dy", "1.2em")
                    .attr("font-size", 8).attr("fill", "#1f2937")
                    .text(d.name.length > 6 ? d.name.slice(0, 6) + "…" : d.name);
            } else {
                el.append("tspan")
                    .attr("x", 0).attr("dy", "0em")
                    .attr("font-size", d.type === "Document" ? 9 : 8)
                    .attr("fill", "#fff")
                    .text(d.name.length > 5 ? d.name.slice(0, 5) + "…" : d.name);
            }
        });

    sim.on("tick", () => {
        link
            .attr("x1", (d: any) => d.source.x)
            .attr("y1", (d: any) => d.source.y)
            .attr("x2", (d: any) => d.target.x)
            .attr("y2", (d: any) => d.target.y);
        linkLabel
            .attr("x", (d: any) => (d.source.x + d.target.x) / 2)
            .attr("y", (d: any) => (d.source.y + d.target.y) / 2 - 4);
        node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });
}

// ── 图例 ──────────────────────────────────────────────────────────────────────
function Legend({ maxRank }: { maxRank: number }) {
    return (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 pb-2 text-xs text-gray-500">
            {Array.from({ length: Math.min(maxRank, 5) }, (_, i) => i + 1).map(rank => (
                <span key={rank} className="flex items-center gap-1">
                    <span className="w-3 h-3 rounded-full inline-block flex-shrink-0"
                          style={{ backgroundColor: rankColor(rank) }} />
                    第 {rank} 位引用
                </span>
            ))}
            <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-full inline-block flex-shrink-0 bg-gray-600" />
                关联上下文
            </span>
        </div>
    );
}

// ── 主组件 ────────────────────────────────────────────────────────────────────
interface Props {
    sources: SourceSection[];
}

export default function SourceGraph({ sources }: Props) {
    const [open,      setOpen]      = useState(false);
    const [maximized, setMaximized] = useState(false);
    const [loading,   setLoading]   = useState(false);
    const [data,      setData]      = useState<{ nodes: GraphNode[]; edges: GraphEdge[] } | null>(null);
    const svgRef     = useRef<SVGSVGElement>(null);
    const svgModalRef = useRef<SVGSVGElement>(null);

    // 懒加载：第一次展开时拉取子图数据
    useEffect(() => {
        if (!open || data) return;
        setLoading(true);
        const ids = sources.map(s => s.chunk_id).join(",");
        const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
        fetch(`http://localhost:8000/api/query/source-graph?chunk_ids=${encodeURIComponent(ids)}`, {
            headers: { "Authorization": `Bearer ${token}` },
        })
            .then(r => r.json())
            .then(d => setData(d))
            .catch(() => setData({ nodes: [], edges: [] }))
            .finally(() => setLoading(false));
    }, [open, data, sources]);

    // 数据就绪后绘制（内嵌视图）
    useEffect(() => {
        if (!open || maximized || !data || !svgRef.current) return;
        drawSourceGraph(svgRef.current, data);
    }, [open, maximized, data]);

    // 数据就绪后绘制（最大化模态）
    useEffect(() => {
        if (!maximized || !data || !svgModalRef.current) return;
        drawSourceGraph(svgModalRef.current, data);
    }, [maximized, data]);

    // 按 Escape 关闭最大化
    useEffect(() => {
        if (!maximized) return;
        const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setMaximized(false); };
        document.addEventListener("keydown", handler);
        return () => document.removeEventListener("keydown", handler);
    }, [maximized]);

    if (sources.length === 0) return null;

    return (
        <>
            <div className="mt-2">
                {/* 切换按钮 */}
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setOpen(v => !v)}
                        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-indigo-400
                                   transition-colors select-none"
                    >
                        <svg className={`w-3 h-3 transition-transform ${open ? "rotate-90" : ""}`}
                             viewBox="0 0 12 12" fill="currentColor">
                            <path d="M4 2l5 4-5 4V2z"/>
                        </svg>
                        {open ? "收起来源图谱" : "展开来源图谱"}
                        <span className="px-1.5 py-0.5 bg-gray-800 rounded text-gray-500">
                            {sources.length} 个来源
                        </span>
                    </button>
                    {open && !loading && data && data.nodes.length > 0 && (
                        <button
                            onClick={() => setMaximized(true)}
                            className="text-xs text-gray-600 hover:text-indigo-400 transition-colors select-none flex items-center gap-1"
                            title="最大化图谱"
                        >
                            <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                                <path d="M1 4V1h3M8 1h3v3M11 8v3H8M4 11H1V8"/>
                            </svg>
                            最大化
                        </button>
                    )}
                </div>

                {open && (
                    <div className="mt-2 rounded-xl border border-gray-700 bg-gray-950 overflow-hidden select-none">
                        {loading ? (
                            <div className="h-52 flex items-center justify-center text-xs text-gray-600">
                                加载图谱中…
                            </div>
                        ) : data && data.nodes.length === 0 ? (
                            <div className="h-24 flex items-center justify-center text-xs text-gray-600">
                                暂无图谱数据
                            </div>
                        ) : (
                            <>
                                <svg ref={svgRef} className="w-full" style={{ height: 260 }} />
                                <Legend maxRank={sources.length} />
                            </>
                        )}
                    </div>
                )}
            </div>

            {/* 最大化模态 */}
            {maximized && (
                <div
                    className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6"
                    onClick={() => setMaximized(false)}
                >
                    <div
                        className="w-full max-w-5xl bg-gray-950 border border-gray-700 rounded-2xl
                                   overflow-hidden flex flex-col"
                        style={{ height: "80vh" }}
                        onClick={e => e.stopPropagation()}
                    >
                        {/* 模态标题栏 */}
                        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
                            <span className="text-sm text-gray-300">来源图谱</span>
                            <button
                                onClick={() => setMaximized(false)}
                                className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                                title="关闭（Esc）"
                            >
                                <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                                    <path d="M4 4l8 8M12 4l-8 8"/>
                                </svg>
                            </button>
                        </div>
                        <div className="flex-1 overflow-hidden">
                            <svg ref={svgModalRef} className="w-full h-full" />
                        </div>
                        <Legend maxRank={sources.length} />
                    </div>
                </div>
            )}
        </>
    );
}
