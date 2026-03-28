"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";

interface GraphNode {
    id: string;
    label: string;
    name: string;
    x?: number;
    y?: number;
}

interface GraphEdge {
    source: string;
    target: string;
    type: string;
}

interface GraphData {
    nodes: GraphNode[];
    edges: GraphEdge[];
}

interface SimNode extends GraphNode {
    x?: number;
    y?: number;
    fx?: number | null;
    fy?: number | null;
}

interface SimEdge {
    source: SimNode | string;
    target: SimNode | string;
    type: string;
}

const MIN_SCALE = 0.3;
const MAX_SCALE = 3;

function drawGraph(data: GraphData, svgEl: SVGSVGElement, tooltipEl: HTMLDivElement, onScaleChange: (s: number) => void,
): d3.ZoomBehavior<SVGSVGElement, unknown> {
    const width = svgEl.clientWidth;
    const height = svgEl.clientHeight;

    d3.select(svgEl).selectAll("*").remove();

    const svg = d3.select(svgEl);

    // 缩放容器 — 所有内容放在 g 里，zoom 作用在 g 上
    const container = svg.append("g");

    // 滚轮缩放
    const zoom = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([MIN_SCALE, MAX_SCALE])
        .on("zoom", (event) => {
            container.attr("transform", event.transform);
            onScaleChange(event.transform.k) // k 是当前缩放值
        });
    // 重置缩放状态
    svg.call(zoom.transform, d3.zoomIdentity);

    const color: Record<string, string> = {
        Document: "#6366f1",
        Section: "#f59e0b",
    };

    const nodeRadius = (d: SimNode) => d.label === "Document" ? 36 : 22;

    const nodeCount = data.nodes.length;
    const chargeStrength = nodeCount > 50 ? -150 : -500;
    const linkDistance = nodeCount > 50 ? 60 : 140;

    (data.nodes as SimNode[]).forEach(node => {
        if (node.x === undefined) {
            node.x = width / 2 + (Math.random() - 0.5) * 100;
            node.y = height / 2 + (Math.random() - 0.5) * 100;
        }
    });

    const simulation = d3.forceSimulation(data.nodes as SimNode[])
        .force("link", d3.forceLink(data.edges)
            .id((d: any) => d.id)
            .distance(linkDistance))
        .force("charge", d3.forceManyBody().strength(chargeStrength))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collide", d3.forceCollide<SimNode>()
            .radius(d => nodeRadius(d) + 8)
            .strength(0.8))
        .alphaDecay(0.03)
        .velocityDecay(0.4);

    const edgeColor: Record<string, string> = {
        HAS_SECTION: "#4f46e5",  // 靛蓝
        REFERENCES: "#059669",  // 绿色
        HAS_SUBSECTION: "#d97706",  // 橙色
        NEXT_SECTION: "#6b7280",  // 灰色
    };
    // 画边
    const link = container.append("g")
        .selectAll("line")
        .data(data.edges)
        .join("line")
        .attr("stroke", (d: any) => edgeColor[d.type] ?? "#374151")
        .attr("stroke-width", (d: any) => d.type === "REFERENCES" ? 2 : 1.5)
        .attr("stroke-opacity", 0.6);

    // 画节点
    const node = container.append("g")
        .selectAll("g")
        .data(data.nodes as SimNode[])
        .join("g")
        .attr("cursor", "pointer")
        .call(d3.drag<any, SimNode>()
            .on("start", (event, d) => {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x; d.fy = d.y;
            })
            .on("drag", (event, d) => {
                d.fx = event.x; d.fy = event.y;
            })
            .on("end", (event, d) => {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null; d.fy = null;
            })
        );

    node.on("click", (event: MouseEvent, d: SimNode) => {
        if (d.label === "Document" && d.name) {
            // 阻止拖拽事件
            if (event.defaultPrevented) return;
            window.location.href = `/library/${d.name}`;
        }
    });

    // 节点圆形
    node.append("circle")
        .attr("r", d => nodeRadius(d))
        .attr("fill", d => color[d.label] ?? "#6b7280")
        .attr("cursor", d => d.label === "Document" ? "pointer" : "grab");

    // hover tooltip — 浏览器原生，鼠标悬停自动显示完整名称
    node
        .on("mouseover", (event: MouseEvent, d) => {
            const t = d3.select(tooltipEl);
            t.classed("hidden", false)
                .style("left", (event.clientX + 12) + "px")
                .style("top", (event.clientY - 8) + "px")
                .text(d.name);
        })
        .on("mousemove", (event: MouseEvent) => {
            d3.select(tooltipEl)
                .style("left", (event.clientX + 12) + "px")
                .style("top", (event.clientY - 8) + "px");
        })
        .on("mouseout", () => {
            d3.select(tooltipEl).classed("hidden", true);
        });

    // 节点文字（截断）
    node.append("text")
        .text(d => d.name.length > 6 ? d.name.slice(0, 6) + "…" : d.name)
        .attr("font-size", d => d.label === "Document" ? 12 : 10)
        .attr("fill", "#fff")
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "central")
        .attr("pointer-events", "none");

    // 每帧更新
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

export default function GraphPage() {
    const svgRef = useRef<SVGSVGElement>(null);
    const tooltipRef = useRef<HTMLDivElement>(null);
    const [data, setData] = useState<GraphData | null>(null);
    const [scale, setScale] = useState(1);
    const [nodeFilter, setNodeFilter] = useState<"全部" | "Document" | "Section">("全部");
    const [edgeFilter, setEdgeFilter] = useState<"全部关系" | "HAS_SECTION" | "REFERENCES" | "HAS_SUBSECTION">("全部关系");

    const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);

    function zoomIn() { if (svgRef.current && zoomRef.current) d3.select(svgRef.current).transition().call(zoomRef.current.scaleBy, 1.3); }
    function zoomOut() { if (svgRef.current && zoomRef.current) d3.select(svgRef.current).transition().call(zoomRef.current.scaleBy, 0.7); }
    function zoomReset() { if (svgRef.current && zoomRef.current) d3.select(svgRef.current).transition().call(zoomRef.current.transform, d3.zoomIdentity); }

    // 第一步：获取数据
    useEffect(() => {
        fetch("/api/graph")
            .then(res => res.json())
            .then(setData);
    }, []);

    // 第二步：数据准备好后开始画图
    useEffect(() => {
        if (!data || !svgRef.current || !tooltipRef.current) return;

        // 深拷贝节点，避免修改原始数据
        const filteredNodes = data.nodes
            .filter(n => nodeFilter === "全部" || n.label === nodeFilter)
            .map(n => ({ ...n, x: undefined, y: undefined }));  // 重置位置

        const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
        const filteredEdges = data.edges
            .filter(e =>
                (edgeFilter === "全部关系" || e.type === edgeFilter) &&
                filteredNodeIds.has(e.source as string) &&
                filteredNodeIds.has(e.target as string)
            )
            .map(e => ({ ...e }));  // 深拷贝边

        zoomRef.current = drawGraph(
            { nodes: filteredNodes, edges: filteredEdges },
            svgRef.current,
            tooltipRef.current,
            setScale,
        );
    }, [data, nodeFilter, edgeFilter]);

    return (
        <div className="relative w-full h-full bg-gray-950">
            {/* 过滤控制栏 */}
            <div className="absolute top-4 left-4 z-10 flex gap-2 flex-wrap">
                {/* 节点类型过滤 */}
                <div className="flex gap-1 bg-gray-900 border border-gray-700 rounded-lg p-1">
                    {(["全部", "Document", "Section"] as const).map(type => (
                        <button
                            key={type}
                            onClick={() => {
                                setNodeFilter(type);
                            }}
                            className={`px-2.5 py-1 rounded text-xs transition-colors ${nodeFilter === type
                                ? "bg-indigo-600 text-white"
                                : "text-gray-400 hover:text-white"
                                }`}
                        >
                            {type}
                        </button>
                    ))}
                </div>
                {/* 关系类型过滤 */}
                <div className="flex gap-1 bg-gray-900 border border-gray-700 rounded-lg p-1">
                    {(["全部关系", "HAS_SECTION", "REFERENCES", "HAS_SUBSECTION"] as const).map(type => (
                        <button
                            key={type}
                            onClick={() => setEdgeFilter(type)}
                            className={`px-2.5 py-1 rounded text-xs transition-colors ${edgeFilter === type
                                ? "bg-indigo-600 text-white"
                                : "text-gray-400 hover:text-white"
                                }`}
                        >
                            {type}
                        </button>
                    ))}
                </div>
            </div>
            {/* 图例 */}
            <div className="absolute top-4 right-4 z-10 flex flex-col gap-1.5
                bg-gray-900 border border-gray-700 rounded-lg px-3 py-2.5">
                <div className="text-xs text-gray-500 mb-1">图例</div>
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-indigo-500 flex-shrink-0" />
                    <span className="text-xs text-gray-400">Document 规范文档</span>
                </div>
                <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full bg-amber-500 flex-shrink-0" />
                    <span className="text-xs text-gray-400">Section 章节</span>
                </div>
                <div className="mt-1 pt-1.5 border-t border-gray-700 space-y-1">
                    <div className="flex items-center gap-2">
                        <div className="w-4 h-0.5 bg-indigo-500 flex-shrink-0" />
                        <span className="text-xs text-gray-500">HAS_SECTION</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-4 h-0.5 bg-emerald-500 flex-shrink-0" />
                        <span className="text-xs text-gray-500">REFERENCES</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <div className="w-4 h-0.5 bg-amber-500 flex-shrink-0" />
                        <span className="text-xs text-gray-500">HAS_SUBSECTION</span>
                    </div>
                </div>
            </div>
            <svg ref={svgRef} className="w-full h-full" />
            {/* 滚轮提示 */}
            <div className="absolute bottom-4 right-4 flex items-center gap-2">
                <span className="text-xs text-gray-500">缩放</span>
                <button
                    onClick={zoomOut}
                    disabled={scale <= MIN_SCALE}
                    className="w-7 h-7 rounded bg-gray-800 text-white text-sm
             hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed
             flex items-center justify-center"
                >−</button>
                <button
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
                    onClick={zoomIn}
                    disabled={scale >= MAX_SCALE}
                    className="w-7 h-7 rounded bg-gray-800 text-white text-sm
             hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed
             flex items-center justify-center"
                >+</button>
            </div>

            {/* Tooltip */}
            <div
                ref={tooltipRef}
                className="fixed hidden px-2 py-1 bg-gray-800 text-white text-xs
                 rounded pointer-events-none border border-gray-700"
            />
        </div>
    )
}