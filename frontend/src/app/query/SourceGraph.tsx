"use client";

import { useEffect, useRef, useState } from "react";
import { SourceSection } from "./types";
import { drawSourceGraph, rankColor, GraphNode, GraphEdge } from "./SourceGraphRenderer";

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
