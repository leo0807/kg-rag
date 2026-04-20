"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import * as d3 from "d3";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RotateCcw, Search, X } from "lucide-react";

/* ── 类型 ─────────────────────────────────────────────────────────────── */
interface RefNode {
    id:            string;
    title:         string;
    ref_out_count: number;
    ref_in_count:  number;
    is_center:     boolean;
    x?:            number;
    y?:            number;
    fx?:           number | null;
    fy?:           number | null;
}

interface RefEdge {
    source: string | RefNode;
    target: string | RefNode;
    weight: number;
}

interface RefStats {
    total_docs:  number;
    total_refs:  number;
    most_cited:  { doc_id: string; count: number } | null;
}

/* ── 헬퍼 ────────────────────────────────────────────────────────────── */
function nodeRadius(n: RefNode) {
    return Math.min(8 + n.ref_in_count * 2, 36);
}

function nodeColor(n: RefNode) {
    if (n.is_center)           return "#22c55e";   // green-500
    if (n.ref_in_count >= 5)   return "#f59e0b";   // amber-400 (核心)
    return "#6366f1";                               // indigo-500
}

const ARROW_ID = "ref-arrow";

/* ══════════════════════════════════════════════════════════════════════ */
export default function ReferencesPage() {
    const svgRef      = useRef<SVGSVGElement>(null);
    const tooltipRef  = useRef<HTMLDivElement>(null);
    const simRef      = useRef<d3.Simulation<RefNode, RefEdge> | null>(null);

    const [nodes,    setNodes]    = useState<RefNode[]>([]);
    const [edges,    setEdges]    = useState<RefEdge[]>([]);
    const [stats,    setStats]    = useState<RefStats | null>(null);
    const [focusId,  setFocusId]  = useState("");
    const [depth,    setDepth]    = useState(1);
    const [search,   setSearch]   = useState("");
    const [selected, setSelected] = useState<RefNode | null>(null);
    const [loading,  setLoading]  = useState(true);
    const router = useRouter();

    /* ── 数据获取 ──────────────────────────────────────────────────── */
    const fetchData = useCallback(async (docId: string, d: number) => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (docId) params.set("doc_id", docId);
            params.set("depth", String(d));
            const res  = await fetch(`/api/graph/references?${params}`);
            const data = await res.json();
            setNodes(data.nodes ?? []);
            setEdges(data.edges ?? []);
            setStats(data.stats ?? null);
        } catch (e) {
            console.error("fetch references failed", e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(focusId, depth); }, [focusId, depth, fetchData]);

    /* ── D3 渲染 ───────────────────────────────────────────────────── */
    useEffect(() => {
        if (loading || !svgRef.current) return;

        const svg = d3.select(svgRef.current);
        svg.selectAll("*").remove();

        const W = svgRef.current.clientWidth  || 900;
        const H = svgRef.current.clientHeight || 600;

        /* 箭头 marker */
        svg.append("defs").append("marker")
            .attr("id",          ARROW_ID)
            .attr("viewBox",     "0 -5 10 10")
            .attr("refX",        20)
            .attr("refY",        0)
            .attr("markerWidth", 6)
            .attr("markerHeight",6)
            .attr("orient",      "auto")
            .append("path")
            .attr("d",    "M0,-5L10,0L0,5")
            .attr("fill", "#4b5563");

        const g    = svg.append("g");

        /* Zoom */
        const zoom = d3.zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.15, 4])
            .on("zoom", ev => g.attr("transform", ev.transform));
        svg.call(zoom);
        svg.on("click.deselect", () => {
            setSelected(null);
            link.attr("stroke", "#374151");
        });

        /* Simulation */
        const simNodes: RefNode[] = nodes.map(n => ({ ...n }));
        const nodeById = new Map(simNodes.map(n => [n.id, n]));
        const simEdges: RefEdge[] = edges.map(e => ({
            source: nodeById.get(e.source as string) ?? (e.source as RefNode),
            target: nodeById.get(e.target as string) ?? (e.target as RefNode),
            weight: e.weight,
        }));

        const sim = d3.forceSimulation(simNodes)
            .force("link",    d3.forceLink<RefNode, RefEdge>(simEdges)
                .id(d => d.id).distance(80).strength(0.6))
            .force("charge",  d3.forceManyBody().strength(-220))
            .force("center",  d3.forceCenter(W / 2, H / 2))
            .force("collide", d3.forceCollide<RefNode>().radius(d => nodeRadius(d) + 6))
            .alphaDecay(0.04);

        simRef.current = sim;

        /* Edges */
        const link = g.append("g").selectAll("line")
            .data(simEdges)
            .join("line")
            .attr("stroke",       "#374151")
            .attr("stroke-width", d => Math.min(1 + d.weight * 0.5, 5))
            .attr("marker-end",   `url(#${ARROW_ID})`)
            .attr("stroke-opacity", 0.7);

        /* Nodes */
        const nodeG = g.append("g").selectAll("g")
            .data(simNodes)
            .join("g")
            .attr("cursor", "pointer")
            .call(
                d3.drag<SVGGElement, RefNode>()
                    .on("start", (ev, d) => {
                        if (!ev.active) sim.alphaTarget(0.3).restart();
                        d.fx = d.x; d.fy = d.y;
                    })
                    .on("drag",  (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
                    .on("end",   (ev, d) => {
                        if (!ev.active) sim.alphaTarget(0);
                        d.fx = null; d.fy = null;
                    }) as never
            );

        /* 圆 */
        nodeG.append("circle")
            .attr("r",    d => nodeRadius(d))
            .attr("fill", d => nodeColor(d))
            .attr("stroke",       d => d.is_center ? "#fff" : "transparent")
            .attr("stroke-width", 2);

        /* 标签 */
        nodeG.append("text")
            .text(d => d.id.length > 8 ? d.id.slice(0, 8) : d.id)
            .attr("text-anchor", "middle")
            .attr("dy",          "0.35em")
            .attr("fill",        "#fff")
            .attr("font-size",   d => `${Math.max(9, Math.min(nodeRadius(d) * 0.55, 13))}px`)
            .attr("pointer-events", "none");

        /* Tooltip + click */
        const tooltip = d3.select(tooltipRef.current!);
        nodeG
            .on("mouseover", (ev, d) => {
                tooltip.classed("hidden", false)
                    .style("left", (ev.clientX + 14) + "px")
                    .style("top",  (ev.clientY - 10) + "px")
                    .html(`<div class="font-semibold">${d.id}</div>
                           <div class="text-gray-400 text-xs mt-0.5">${d.title}</div>
                           <div class="text-xs mt-1">引出 ${d.ref_out_count} / 被引 ${d.ref_in_count}</div>`);
            })
            .on("mousemove", ev => {
                tooltip
                    .style("left", (ev.clientX + 14) + "px")
                    .style("top",  (ev.clientY - 10) + "px");
            })
            .on("mouseout", () => tooltip.classed("hidden", true))
            .on("click", (ev, d) => {
                ev.stopPropagation();
                setSelected(d);
                link.attr("stroke", e => {
                    const s = (e.source as RefNode).id;
                    const t = (e.target as RefNode).id;
                    return s === d.id || t === d.id ? "#f97316" : "#374151";
                });
            })
            .on("dblclick", (ev, d) => {
                ev.stopPropagation();
                router.push(`/library/${d.id}`);
            });

        /* Tick */
        sim.on("tick", () => {
            link
                .attr("x1", d => (d.source as RefNode).x ?? 0)
                .attr("y1", d => (d.source as RefNode).y ?? 0)
                .attr("x2", d => (d.target as RefNode).x ?? 0)
                .attr("y2", d => (d.target as RefNode).y ?? 0);
            nodeG.attr("transform", d => `translate(${d.x ?? 0},${d.y ?? 0})`);
        });

        return () => { sim.stop(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [nodes, edges, loading]);

    /* ── 搜索过滤 ──────────────────────────────────────────────────── */
    const filtered = search.trim()
        ? nodes.filter(n =>
            n.id.toLowerCase().includes(search.toLowerCase()) ||
            n.title.toLowerCase().includes(search.toLowerCase()))
        : [];

    /* ── 右侧面板：选中节点的出入邻居 ─────────────────────────────── */
    const outNeighbors = selected
        ? edges.flatMap(e => {
            const s = typeof e.source === "string" ? e.source : (e.source as RefNode).id;
            const t = typeof e.target === "string" ? e.target : (e.target as RefNode).id;
            return s === selected.id ? [t] : [];
          })
        : [];
    const inNeighbors = selected
        ? edges.flatMap(e => {
            const s = typeof e.source === "string" ? e.source : (e.source as RefNode).id;
            const t = typeof e.target === "string" ? e.target : (e.target as RefNode).id;
            return t === selected.id ? [s] : [];
          })
        : [];

    /* ── JSX ──────────────────────────────────────────────────────── */
    return (
        <div className="flex h-full bg-gray-950 overflow-hidden">

            {/* ── 左侧控制面板 ── */}
            <div className="w-56 shrink-0 flex flex-col border-r border-gray-800 bg-gray-900 overflow-y-auto">
                <div className="px-4 py-4 border-b border-gray-800">
                    <h1 className="text-sm font-bold text-white">引用关系图</h1>
                    <p className="text-xs text-gray-500 mt-0.5">文档间规范引用网络</p>
                </div>

                {/* 搜索 */}
                <div className="px-3 py-3 border-b border-gray-800">
                    <div className="relative">
                        <Search size={13} className="absolute left-2.5 top-2 text-gray-500" />
                        <input
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            placeholder="搜索文档编号…"
                            className="w-full pl-8 pr-2 py-1.5 bg-gray-800 border border-gray-700
                                       rounded-lg text-xs text-gray-200 placeholder-gray-600
                                       outline-none focus:border-indigo-500"
                        />
                    </div>
                    {filtered.length > 0 && (
                        <div className="mt-1 bg-gray-800 border border-gray-700 rounded-lg overflow-hidden max-h-40 overflow-y-auto">
                            {filtered.map(n => (
                                <button key={n.id}
                                    onClick={() => { setFocusId(n.id); setSearch(""); setSelected(null); }}
                                    className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700 truncate">
                                    <span className="font-mono text-indigo-400">{n.id}</span>
                                    <span className="text-gray-500 ml-1">{n.title.slice(0, 20)}</span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* 当前聚焦 */}
                {focusId && (
                    <div className="px-3 py-2 border-b border-gray-800 flex items-center gap-2">
                        <span className="text-xs text-indigo-400 font-mono truncate flex-1">{focusId}</span>
                        <button onClick={() => { setFocusId(""); setSelected(null); }}
                            className="text-gray-500 hover:text-white">
                            <X size={12} />
                        </button>
                    </div>
                )}

                {/* 深度 */}
                {focusId && (
                    <div className="px-3 py-3 border-b border-gray-800">
                        <div className="text-xs text-gray-500 mb-2">扩散深度</div>
                        <div className="flex gap-1">
                            {[1, 2].map(d => (
                                <button key={d} onClick={() => setDepth(d)}
                                    className={`flex-1 py-1 text-xs rounded border transition-colors ${
                                        depth === d
                                            ? "bg-indigo-600 border-indigo-500 text-white"
                                            : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white"
                                    }`}>
                                    {d} 跳
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* 统计 */}
                {stats && (
                    <div className="px-3 py-3 border-b border-gray-800 space-y-2">
                        <div className="text-xs text-gray-500 uppercase tracking-wider">统计</div>
                        <div className="text-xs text-gray-300">
                            <div className="flex justify-between">
                                <span className="text-gray-500">文档数</span>
                                <span>{stats.total_docs}</span>
                            </div>
                            <div className="flex justify-between mt-1">
                                <span className="text-gray-500">引用数</span>
                                <span>{stats.total_refs}</span>
                            </div>
                            {stats.most_cited && (
                                <div className="mt-2 px-2 py-1.5 bg-amber-950/30 border border-amber-800/40 rounded-lg">
                                    <div className="text-amber-400/70 text-[10px] mb-0.5">被引最多</div>
                                    <div className="text-amber-300 font-mono text-xs">{stats.most_cited.doc_id}</div>
                                    <div className="text-amber-400/60 text-[10px]">{stats.most_cited.count} 次</div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* 图例 */}
                <div className="px-3 py-3 space-y-1.5">
                    <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">图例</div>
                    {[
                        ["#22c55e", "当前文档"],
                        ["#f59e0b", "核心文档（≥5次被引）"],
                        ["#6366f1", "普通文档"],
                    ].map(([color, label]) => (
                        <div key={label} className="flex items-center gap-2">
                            <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: color }} />
                            <span className="text-xs text-gray-400">{label}</span>
                        </div>
                    ))}
                </div>

                {/* 重置 */}
                <div className="mt-auto px-3 py-3 border-t border-gray-800">
                    <button
                        onClick={() => { setFocusId(""); setDepth(1); setSelected(null); }}
                        className="w-full flex items-center justify-center gap-1.5 py-1.5 text-xs
                                   text-gray-400 hover:text-white border border-gray-700
                                   hover:border-gray-500 rounded-lg transition-colors">
                        <RotateCcw size={12} /> 重置视图
                    </button>
                </div>
            </div>

            {/* ── 主图区 ── */}
            <div className="flex-1 relative overflow-hidden">
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center z-10 bg-gray-950/60">
                        <div className="text-gray-400 text-sm animate-pulse">加载引用关系图…</div>
                    </div>
                )}

                <svg ref={svgRef} className="w-full h-full" />

                {/* Tooltip */}
                <div
                    ref={tooltipRef}
                    className="hidden fixed z-50 px-3 py-2 bg-gray-900 border border-gray-700
                               rounded-xl text-sm text-gray-200 shadow-xl pointer-events-none max-w-xs"
                />
            </div>

            {/* ── 右侧详情面板 ── */}
            {selected && (
                <div className="w-60 shrink-0 border-l border-gray-800 bg-gray-900 overflow-y-auto flex flex-col">
                    <div className="px-4 py-4 border-b border-gray-800 flex items-start justify-between gap-2">
                        <div>
                            <div className="text-sm font-bold text-white font-mono">{selected.id}</div>
                            <div className="text-xs text-gray-400 mt-0.5 leading-relaxed">{selected.title}</div>
                        </div>
                        <button onClick={() => setSelected(null)} className="text-gray-600 hover:text-white mt-0.5">
                            <X size={14} />
                        </button>
                    </div>

                    {/* 引出 */}
                    <div className="px-4 py-3 border-b border-gray-800">
                        <div className="text-xs text-gray-500 mb-2">
                            引用了 <span className="text-gray-300">{outNeighbors.length}</span> 份文档
                        </div>
                        {outNeighbors.length === 0
                            ? <p className="text-xs text-gray-600">—</p>
                            : <div className="space-y-1">
                                {outNeighbors.map(id => (
                                    <button key={id} onClick={() => { setFocusId(id); setSelected(null); }}
                                        className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                                        <span className="text-gray-600">→</span>
                                        <span className="font-mono">{id}</span>
                                    </button>
                                ))}
                            </div>
                        }
                    </div>

                    {/* 引入 */}
                    <div className="px-4 py-3 border-b border-gray-800">
                        <div className="text-xs text-gray-500 mb-2">
                            被 <span className="text-gray-300">{inNeighbors.length}</span> 份文档引用
                        </div>
                        {inNeighbors.length === 0
                            ? <p className="text-xs text-gray-600">—</p>
                            : <div className="space-y-1">
                                {inNeighbors.map(id => (
                                    <button key={id} onClick={() => { setFocusId(id); setSelected(null); }}
                                        className="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 transition-colors">
                                        <span className="text-gray-600">←</span>
                                        <span className="font-mono">{id}</span>
                                    </button>
                                ))}
                            </div>
                        }
                    </div>

                    {/* 操作 */}
                    <div className="px-4 py-3 flex flex-col gap-2">
                        <Link href={`/library/${selected.id}`}
                            className="w-full text-center py-1.5 text-xs bg-indigo-600 hover:bg-indigo-700
                                       text-white rounded-lg transition-colors">
                            查看文档
                        </Link>
                        <Link href={`/query?q=${encodeURIComponent(selected.id)}`}
                            className="w-full text-center py-1.5 text-xs bg-gray-800 hover:bg-gray-700
                                       border border-gray-700 text-gray-300 rounded-lg transition-colors">
                            在此问答
                        </Link>
                        {!selected.is_center && (
                            <button onClick={() => { setFocusId(selected.id); setSelected(null); }}
                                className="w-full text-center py-1.5 text-xs bg-gray-800 hover:bg-gray-700
                                           border border-gray-700 text-gray-300 rounded-lg transition-colors">
                                聚焦此文档
                            </button>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
