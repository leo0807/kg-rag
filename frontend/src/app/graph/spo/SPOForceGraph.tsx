"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";

interface SPONode { node_id: string; name: string; type: string; graph_id: string }
interface SPOEdge { source: string; target: string; predicate: string; predicate_type: string }

interface SimNode extends d3.SimulationNodeDatum {
  node_id: string; name: string; type: string; graph_id: string;
}
interface SimEdge extends d3.SimulationLinkDatum<SimNode> {
  predicate: string; predicate_type: string;
}

interface Props { nodes: SPONode[]; edges: SPOEdge[] }

const TYPE_COLOR: Record<string, string> = {
  System:       "#6366f1",
  Component:    "#8b5cf6",
  Process:      "#10b981",
  Material:     "#f59e0b",
  Tool:         "#06b6d4",
  Parameter:    "#ec4899",
  Standard:     "#3b82f6",
  Requirement:  "#ef4444",
  Organization: "#84cc16",
  Concept:      "#9ca3af",
};

function nodeColor(type: string) {
  return TYPE_COLOR[type] ?? "#6b7280";
}

export function SPOForceGraph({ nodes, edges }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const el   = svgRef.current;
    const W    = el.clientWidth  || 900;
    const H    = el.clientHeight || 560;
    const svg  = d3.select(el);
    svg.selectAll("*").remove();

    const g = svg.append("g");

    // Zoom
    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.2, 4])
        .on("zoom", (e) => g.attr("transform", e.transform)),
    );

    // Arrow marker
    svg.append("defs").append("marker")
      .attr("id", "arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 22).attr("refY", 0)
      .attr("markerWidth", 6).attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "#4b5563");

    // Build simulation data
    const simNodes: SimNode[] = nodes.map(n => ({ ...n, x: W / 2, y: H / 2 }));
    const idIdx = new Map(simNodes.map((n, i) => [n.node_id, i]));
    const simEdges: SimEdge[] = edges
      .filter(e => idIdx.has(e.source) && idIdx.has(e.target))
      .map(e => ({ ...e, source: idIdx.get(e.source)!, target: idIdx.get(e.target)! }));

    const simulation = d3.forceSimulation<SimNode>(simNodes)
      .force("link",   d3.forceLink<SimNode, SimEdge>(simEdges).id((_, i) => i).distance(120).strength(0.6))
      .force("charge", d3.forceManyBody().strength(-280))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collide", d3.forceCollide(28));

    // Edges
    const link = g.append("g").selectAll("line")
      .data(simEdges).join("line")
      .attr("stroke", "#374151")
      .attr("stroke-width", 1.5)
      .attr("marker-end", "url(#arrow)");

    // Edge labels
    const edgeLabel = g.append("g").selectAll("text")
      .data(simEdges).join("text")
      .text(d => d.predicate.length > 10 ? d.predicate.slice(0, 10) + "…" : d.predicate)
      .attr("fill", "#6b7280")
      .attr("font-size", 9)
      .attr("text-anchor", "middle");

    // Nodes (draggable)
    const node = g.append("g").selectAll<SVGGElement, SimNode>("g")
      .data(simNodes).join("g")
      .attr("cursor", "pointer")
      .call(
        d3.drag<SVGGElement, SimNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
          })
          .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
          }),
      );

    node.append("circle")
      .attr("r", 14)
      .attr("fill", d => nodeColor(d.type))
      .attr("fill-opacity", 0.85)
      .attr("stroke", "#1f2937")
      .attr("stroke-width", 2);

    node.append("text")
      .text(d => d.name.length > 8 ? d.name.slice(0, 8) + "…" : d.name)
      .attr("dy", 28).attr("text-anchor", "middle")
      .attr("fill", "#d1d5db").attr("font-size", 10);

    // Tooltip
    node.append("title").text(d => `[${d.type}] ${d.name}`);

    simulation.on("tick", () => {
      link
        .attr("x1", d => (d.source as SimNode).x ?? 0)
        .attr("y1", d => (d.source as SimNode).y ?? 0)
        .attr("x2", d => (d.target as SimNode).x ?? 0)
        .attr("y2", d => (d.target as SimNode).y ?? 0);

      edgeLabel
        .attr("x", d => (((d.source as SimNode).x ?? 0) + ((d.target as SimNode).x ?? 0)) / 2)
        .attr("y", d => (((d.source as SimNode).y ?? 0) + ((d.target as SimNode).y ?? 0)) / 2 - 4);

      node.attr("transform", d => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    return () => { simulation.stop(); };
  }, [nodes, edges]);

  return (
    <svg ref={svgRef} className="w-full h-full" style={{ background: "#030712" }} />
  );
}
