"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import { useRouter } from "next/navigation";
import type { RefNode, RefEdge, ImplicitEdge } from "./useReferences";
import { nodeRadius, nodeColor } from "./useReferences";

const ARROW_ID = "ref-arrow";

const IMPLICIT_ARROW_ID = "implicit-arrow";

interface Props {
    nodes: RefNode[];
    edges: RefEdge[];
    loading: boolean;
    onSelect: (node: RefNode | null) => void;
    implicitEdges?: ImplicitEdge[];
    showImplicit?: boolean;
}

export function ReferenceGraph({ nodes, edges, loading, onSelect, implicitEdges = [], showImplicit = false }: Props) {
    const svgRef     = useRef<SVGSVGElement>(null);
    const tooltipRef = useRef<HTMLDivElement>(null);
    const router     = useRouter();

    useEffect(() => {
        if (loading || !svgRef.current) return;

        const svg = d3.select(svgRef.current);
        svg.selectAll("*").remove();

        const W = svgRef.current.clientWidth  || 900;
        const H = svgRef.current.clientHeight || 600;

        const defs = svg.append("defs");
        defs.append("marker")
            .attr("id",           ARROW_ID)
            .attr("viewBox",      "0 -5 10 10")
            .attr("refX",         20)
            .attr("refY",         0)
            .attr("markerWidth",  6)
            .attr("markerHeight", 6)
            .attr("orient",       "auto")
            .append("path")
            .attr("d",    "M0,-5L10,0L0,5")
            .attr("fill", "#4b5563");
        // 隐性关联箭头（绿色）
        defs.append("marker")
            .attr("id",           IMPLICIT_ARROW_ID)
            .attr("viewBox",      "0 -5 10 10")
            .attr("refX",         20)
            .attr("refY",         0)
            .attr("markerWidth",  6)
            .attr("markerHeight", 6)
            .attr("orient",       "auto")
            .append("path")
            .attr("d",    "M0,-5L10,0L0,5")
            .attr("fill", "#22c55e");

        const g    = svg.append("g");
        const zoom = d3.zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.15, 4])
            .on("zoom", ev => g.attr("transform", ev.transform));
        svg.call(zoom);
        svg.on("click.deselect", () => {
            onSelect(null);
            link.attr("stroke", "#374151");
        });

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

        const link = g.append("g").selectAll("line")
            .data(simEdges).join("line")
            .attr("stroke",         "#374151")
            .attr("stroke-width",   d => Math.min(1 + d.weight * 0.5, 5))
            .attr("marker-end",     `url(#${ARROW_ID})`)
            .attr("stroke-opacity", 0.7);

        const nodeG = g.append("g").selectAll("g")
            .data(simNodes).join("g")
            .attr("cursor", "pointer")
            .call(
                d3.drag<SVGGElement, RefNode>()
                    .on("start", (ev, d) => { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
                    .on("drag",  (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
                    .on("end",   (ev, d) => { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }) as never
            );

        nodeG.append("circle")
            .attr("r",            d => nodeRadius(d))
            .attr("fill",         d => nodeColor(d))
            .attr("stroke",       d => d.is_center ? "#fff" : "transparent")
            .attr("stroke-width", 2);

        nodeG.append("text")
            .text(d => d.id.length > 8 ? d.id.slice(0, 8) : d.id)
            .attr("text-anchor",   "middle")
            .attr("dy",            "0.35em")
            .attr("fill",          "#fff")
            .attr("font-size",     d => `${Math.max(9, Math.min(nodeRadius(d) * 0.55, 13))}px`)
            .attr("pointer-events","none");

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
                tooltip.style("left", (ev.clientX + 14) + "px").style("top", (ev.clientY - 10) + "px");
            })
            .on("mouseout", () => tooltip.classed("hidden", true))
            .on("click", (ev, d) => {
                ev.stopPropagation();
                onSelect(d);
                link.attr("stroke", e => {
                    const s = (e.source as RefNode).id;
                    const t = (e.target as RefNode).id;
                    return s === d.id || t === d.id ? "#f97316" : "#374151";
                });
            })
            .on("dblclick", (ev, d) => { ev.stopPropagation(); router.push(`/library/${d.id}`); });

        // 隐性关联虚线覆盖层（在节点之前，避免遮挡）
        const implicitFiltered = showImplicit
            ? implicitEdges.filter(ie =>
                nodeById.has(ie.doc_a) && nodeById.has(ie.doc_b))
            : [];

        const implicitLayer = g.insert("g", "g + g").selectAll("line")
            .data(implicitFiltered).join("line")
            .attr("stroke",           "#22c55e")
            .attr("stroke-width",     1.5)
            .attr("stroke-dasharray", "5,4")
            .attr("stroke-opacity",   0.65)
            .attr("marker-end",       `url(#${IMPLICIT_ARROW_ID})`);

        const implicitTooltip = d3.select(tooltipRef.current!);
        implicitLayer
            .on("mouseover", (ev, d: ImplicitEdge) => {
                implicitTooltip.classed("hidden", false)
                    .style("left", (ev.clientX + 14) + "px")
                    .style("top",  (ev.clientY - 10) + "px")
                    .html(`<div class="text-emerald-400 font-semibold text-xs mb-1">隐性关联</div>
                           <div class="text-xs text-gray-300">共同涉及：${d.common_entities.slice(0, 4).join("、")}</div>
                           <div class="text-xs text-gray-500 mt-0.5">置信度 ${(d.confidence * 100).toFixed(0)}%</div>`);
            })
            .on("mousemove", ev => {
                implicitTooltip.style("left", (ev.clientX + 14) + "px").style("top", (ev.clientY - 10) + "px");
            })
            .on("mouseout", () => implicitTooltip.classed("hidden", true));

        sim.on("tick", () => {
            link
                .attr("x1", d => (d.source as RefNode).x ?? 0)
                .attr("y1", d => (d.source as RefNode).y ?? 0)
                .attr("x2", d => (d.target as RefNode).x ?? 0)
                .attr("y2", d => (d.target as RefNode).y ?? 0);
            nodeG.attr("transform", d => `translate(${d.x ?? 0},${d.y ?? 0})`);
            implicitLayer
                .attr("x1", d => (nodeById.get(d.doc_a)?.x) ?? 0)
                .attr("y1", d => (nodeById.get(d.doc_a)?.y) ?? 0)
                .attr("x2", d => (nodeById.get(d.doc_b)?.x) ?? 0)
                .attr("y2", d => (nodeById.get(d.doc_b)?.y) ?? 0);
        });

        return () => { sim.stop(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [nodes, edges, loading, implicitEdges, showImplicit]);

    return (
        <div className="flex-1 relative overflow-hidden">
            {loading && (
                <div className="absolute inset-0 flex items-center justify-center z-10 bg-gray-950/60">
                    <div className="text-gray-400 text-sm animate-pulse">加载引用关系图…</div>
                </div>
            )}
            <svg ref={svgRef} className="w-full h-full" />
            <div
                ref={tooltipRef}
                className="hidden fixed z-50 px-3 py-2 bg-gray-900 border border-gray-700
                           rounded-xl text-sm text-gray-200 shadow-xl pointer-events-none max-w-xs"
            />
        </div>
    );
}
