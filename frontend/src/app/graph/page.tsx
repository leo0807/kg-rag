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
    svg.call(zoom);

    const color: Record<string, string> = {
        Document: "#6366f1",
        Section: "#f59e0b",
    };

    const nodeRadius = (d: SimNode) => d.label === "Document" ? 36 : 22;

    const simulation = d3.forceSimulation(data.nodes as SimNode[])
        .force("link", d3.forceLink(data.edges)
            .id((d: any) => d.id)
            .distance(140))
        .force("charge", d3.forceManyBody().strength(-500))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collide", d3.forceCollide<SimNode>()
            .radius(d => nodeRadius(d) + 10)  // 节点半径 + 10px 间距
            .strength(1));                     // 强度 1 = 完全防重叠

    // 画边
    const link = container.append("g")
        .selectAll("line")
        .data(data.edges)
        .join("line")
        .attr("stroke", "#374151")
        .attr("stroke-width", 1.5);

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

    // 节点圆形
    node.append("circle")
        .attr("r", d => nodeRadius(d))
        .attr("fill", d => color[d.label] ?? "#6b7280");

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
        zoomRef.current = drawGraph(data, svgRef.current, tooltipRef.current, setScale,);
    }, [data]);

    return (
        <div className="w-full h-full bg-gray-950">
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
                    onClick={zoomReset}
                    className="px-2 h-7 rounded bg-gray-800 text-xs text-gray-300 hover:bg-gray-700"
                >重置</button>

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