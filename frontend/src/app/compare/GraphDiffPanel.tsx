"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";

export interface GraphNode {
    id: string;
    label: string;
    type: string;
    status: "added" | "removed" | "unchanged";
}

export interface GraphEdge {
    from: string;
    to: string;
    type: string;
    status: "added" | "removed" | "unchanged";
}

export interface GraphChanges {
    nodes: GraphNode[];
    edges: GraphEdge[];
    stats: {
        added_nodes: number;
        removed_nodes: number;
        unchanged_nodes: number;
        added_edges: number;
        removed_edges: number;
    };
}

const NODE_COLOR: Record<string, string> = {
    added:     "#22c55e",
    removed:   "#ef4444",
    unchanged: "#6b7280",
};
const EDGE_COLOR: Record<string, string> = {
    added:     "#16a34a",
    removed:   "#dc2626",
    unchanged: "#374151",
};

interface Props { changes: GraphChanges }

export function GraphDiffPanel({ changes }: Props) {
    const svgRef = useRef<SVGSVGElement>(null);

    useEffect(() => {
        const svg = svgRef.current;
        if (!svg || changes.nodes.length === 0) return;

        const W = svg.clientWidth || 700;
        const H = 340;
        svg.setAttribute("height", String(H));

        d3.select(svg).selectAll("*").remove();

        const root = d3.select(svg).append("g");

        // arrow markers
        const defs = root.append("defs");
        (["added", "removed", "unchanged"] as const).forEach(s => {
            defs.append("marker")
                .attr("id", `arr-${s}`)
                .attr("viewBox", "0 -4 8 8")
                .attr("refX", 18).attr("refY", 0)
                .attr("markerWidth", 5).attr("markerHeight", 5)
                .attr("orient", "auto")
                .append("path")
                .attr("d", "M0,-4L8,0L0,4")
                .attr("fill", EDGE_COLOR[s]);
        });

        const nodeMap = new Map(changes.nodes.map(n => [n.id, n]));
        const links = changes.edges
            .filter(e => nodeMap.has(e.from) && nodeMap.has(e.to))
            .map(e => ({ ...e, source: e.from, target: e.to }));

        const sim = d3.forceSimulation(changes.nodes as d3.SimulationNodeDatum[])
            .force("link", d3.forceLink(links).id((d: d3.SimulationNodeDatum) => (d as GraphNode).id).distance(80))
            .force("charge", d3.forceManyBody().strength(-120))
            .force("center", d3.forceCenter(W / 2, H / 2))
            .force("collision", d3.forceCollide(22));

        const line = root.append("g").selectAll("line")
            .data(links).join("line")
            .attr("stroke", d => EDGE_COLOR[(d as GraphEdge).status])
            .attr("stroke-width", 1.5)
            .attr("stroke-dasharray", d => (d as GraphEdge).status === "removed" ? "4,3" : null)
            .attr("marker-end", d => `url(#arr-${(d as GraphEdge).status})`);

        const nodeG = root.append("g").selectAll("g")
            .data(changes.nodes).join("g")
            .call(d3.drag<SVGGElement, GraphNode>()
                .on("start", (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); const n = d as unknown as d3.SimulationNodeDatum; n.fx = n.x; n.fy = n.y; })
                .on("drag",  (event, d) => { const n = d as unknown as d3.SimulationNodeDatum; n.fx = event.x; n.fy = event.y; })
                .on("end",   (event, d) => { if (!event.active) sim.alphaTarget(0); const n = d as unknown as d3.SimulationNodeDatum; n.fx = null; n.fy = null; }) as never);

        nodeG.append("circle")
            .attr("r", 14)
            .attr("fill", (d: GraphNode) => NODE_COLOR[d.status] + "33")
            .attr("stroke", (d: GraphNode) => NODE_COLOR[d.status])
            .attr("stroke-width", 2);

        nodeG.append("text")
            .attr("text-anchor", "middle").attr("dy", "0.35em")
            .attr("font-size", 9).attr("fill", "#d1d5db")
            .text((d: GraphNode) => (d.label || "").slice(0, 8));

        nodeG.append("title").text((d: GraphNode) => `${d.type}: ${d.label} [${d.status}]`);

        sim.on("tick", () => {
            line
                .attr("x1", d => (d.source as d3.SimulationNodeDatum).x ?? 0)
                .attr("y1", d => (d.source as d3.SimulationNodeDatum).y ?? 0)
                .attr("x2", d => (d.target as d3.SimulationNodeDatum).x ?? 0)
                .attr("y2", d => (d.target as d3.SimulationNodeDatum).y ?? 0);
            nodeG.attr("transform", d => `translate(${(d as d3.SimulationNodeDatum).x ?? 0},${(d as d3.SimulationNodeDatum).y ?? 0})`);
        });

        return () => { sim.stop(); };
    }, [changes]);

    const { stats } = changes;
    const isEmpty = changes.nodes.length === 0;

    return (
        <div className="border-t border-gray-800 bg-gray-950">
            <div className="flex items-center gap-4 px-6 py-3 border-b border-gray-800">
                <span className="text-xs font-medium text-gray-300">实体图谱变更</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 border border-green-500/30">+{stats.added_nodes} 节点</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30">-{stats.removed_nodes} 节点</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 border border-green-500/30">+{stats.added_edges} 关系</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30">-{stats.removed_edges} 关系</span>
                <div className="ml-auto flex items-center gap-3 text-[10px] text-gray-500">
                    <span><span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-1" />新增</span>
                    <span><span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-1" />删除</span>
                    <span><span className="inline-block w-2 h-2 rounded-full bg-gray-500 mr-1" />不变</span>
                </div>
            </div>
            {isEmpty ? (
                <div className="flex items-center justify-center h-24 text-xs text-gray-600">两篇文档无实体节点数据</div>
            ) : (
                <svg ref={svgRef} width="100%" className="block" />
            )}
        </div>
    );
}
