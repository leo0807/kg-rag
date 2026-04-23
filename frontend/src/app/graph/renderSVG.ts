import * as d3 from "d3";
import { GraphData, GraphNode, SimNode, NODE_COLOR, EDGE_COLOR, MIN_SCALE, MAX_SCALE, nodeRadius } from "./constants";

export function drawGraph(
    data: GraphData,
    svgEl: SVGSVGElement,
    tooltipEl: HTMLDivElement,
    onScaleChange: (s: number) => void,
    onNodeClick: (node: GraphNode) => void,
    highlightedIds: Set<string>,
    heatMap: Map<string, number>,
    tourNodeIds?: Set<string>,
    tourCurrentId?: string,
    isDarkTheme = true,
): d3.ZoomBehavior<SVGSVGElement, unknown> {
    const labelFill = isDarkTheme ? "#ffffff" : "#0f172a";
    const mutedLabelFill = isDarkTheme ? "#475569" : "#64748b";
    const width  = svgEl.clientWidth;
    const height = svgEl.clientHeight;
    const tourMode = (tourNodeIds?.size ?? 0) > 0;

    d3.select(svgEl).selectAll("*").remove();
    const svg       = d3.select(svgEl);
    const container = svg.append("g");

    const zoom = d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([MIN_SCALE, MAX_SCALE])
        .on("zoom", event => { container.attr("transform", event.transform); onScaleChange(event.transform.k); });
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
        .force("collide", d3.forceCollide<SimNode>().radius(d => nodeRadius(d, heatMap.get(d.id) ?? 0) + 8).strength(0.8))
        .alphaDecay(0.03).velocityDecay(0.4);

    const link = container.append("g")
        .selectAll("line").data(data.edges).join("line")
        .attr("stroke",         (d: any) => EDGE_COLOR[d.type] ?? "#374151")
        .attr("stroke-width",   (d: any) => d.type === "REFERENCES" ? 2 : 1.5)
        .attr("stroke-opacity", (d: any) => {
            if (!tourMode) return 0.6;
            const s = typeof d.source === "string" ? d.source : (d.source as GraphNode).id;
            const t = typeof d.target === "string" ? d.target : (d.target as GraphNode).id;
            return (tourNodeIds!.has(s) && tourNodeIds!.has(t)) ? 0.85 : 0.05;
        })
        .attr("stroke-dasharray", (d: any) =>
            d.type === "HAS_IMAGE" || d.type === "MENTIONS_TOOL" || d.type === "HAS_ANNOTATION" ? "4 2" : null
        );

    const node = container.append("g")
        .selectAll("g").data(data.nodes as SimNode[]).join("g")
        .attr("cursor", "pointer")
        .call(
            d3.drag<any, SimNode>()
                .filter(event => event.button === 0)
                .on("start", (event, d) => { event.sourceEvent.stopPropagation(); if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
                .on("drag",  (event, d) => { d.fx = event.x; d.fy = event.y; })
                .on("end",   (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
        );

    node.on("click", (event: MouseEvent, d: SimNode) => { if (event.defaultPrevented) return; onNodeClick(d as GraphNode); });

    if (!tourMode) {
        node.filter(d => (d.type || d.label) === "Section" && (heatMap.get(d.id) ?? 0) > 0.15)
            .append("circle")
            .attr("r",              d => nodeRadius(d, heatMap.get(d.id) ?? 0) + 7)
            .attr("fill",           "none").attr("stroke", "#f59e0b")
            .attr("stroke-width",   d => 1.5 + (heatMap.get(d.id) ?? 0) * 3)
            .attr("stroke-opacity", d => 0.25 + (heatMap.get(d.id) ?? 0) * 0.45);
    }
    if (tourMode && tourCurrentId) {
        node.filter(d => d.id === tourCurrentId)
            .append("circle")
            .attr("r",              d => nodeRadius(d, heatMap.get(d.id) ?? 0) + 11)
            .attr("fill",           "none").attr("stroke", "#fbbf24")
            .attr("stroke-width",   3.5).attr("stroke-opacity", 0.75);
    }
    if (!tourMode) {
        node.filter(d => highlightedIds.has(d.id))
            .append("circle")
            .attr("r",              d => nodeRadius(d, heatMap.get(d.id) ?? 0) + 6)
            .attr("fill",           "none").attr("stroke", "#f97316")
            .attr("stroke-width",   2.5).attr("stroke-opacity", 0.9);
    }

    node.append("circle")
        .attr("r",    d => nodeRadius(d, heatMap.get(d.id) ?? 0))
        .attr("fill", d => NODE_COLOR[d.type || d.label] ?? "#6b7280")
        .attr("opacity", d => {
            if (!tourMode) return 0.95;
            if (d.id === tourCurrentId)  return 1;
            if (tourNodeIds!.has(d.id))  return 0.72;
            return 0.1;
        })
        .attr("stroke",       d => d.id === tourCurrentId ? "#fbbf24" : (highlightedIds.has(d.id) ? "#f97316" : "none"))
        .attr("stroke-width", 2.5);

    node
        .on("mouseover", (event: MouseEvent, d) => {
            const t    = d3.select(tooltipEl);
            const desc = (d as any).description || (d as any).content;
            t.classed("hidden", false)
                .style("left", (event.clientX + 12) + "px")
                .style("top",  (event.clientY - 8)  + "px")
                .html(desc
                    ? `<div class="font-medium">${d.name}</div><div class="text-gray-400 mt-1 max-w-xs">${String(desc).slice(0, 80)}…</div>`
                    : d.name
                );
        })
        .on("mousemove", (event: MouseEvent) => {
            d3.select(tooltipEl).style("left", (event.clientX + 12) + "px").style("top", (event.clientY - 8) + "px");
        })
        .on("mouseout", () => { d3.select(tooltipEl).classed("hidden", true); });

    node.append("text")
        .text(d => { const name = d.name || d.label || ""; return name.length > 6 ? name.slice(0, 6) + "…" : name; })
        .attr("font-size",         d => (d.type || d.label) === "Document" ? 12 : 10)
        .attr("fill",              d => tourMode && !tourNodeIds!.has(d.id) && d.id !== tourCurrentId ? mutedLabelFill : labelFill)
        .attr("text-anchor",       "middle")
        .attr("dominant-baseline", "central")
        .attr("pointer-events",    "none");

    simulation.on("tick", () => {
        link.attr("x1", (d: any) => d.source.x).attr("y1", (d: any) => d.source.y)
            .attr("x2", (d: any) => d.target.x).attr("y2", (d: any) => d.target.y);
        node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });

    return zoom;
}
