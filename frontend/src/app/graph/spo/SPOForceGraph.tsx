"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";

interface SPONode { node_id: string; name: string; type: string; graph_id: string }
interface SPOEdge { source: string; target: string; predicate: string; predicate_type: string }

interface SimNode extends d3.SimulationNodeDatum {
  node_id: string; name: string; type: string;
}
interface SimEdge extends d3.SimulationLinkDatum<SimNode> {
  predicate: string; predicate_type: string;
}

interface Props { nodes: SPONode[]; edges: SPOEdge[] }

const TYPE_COLOR: Record<string, string> = {
  System: "#6366f1", Component: "#8b5cf6", Process: "#10b981",
  Material: "#f59e0b", Tool: "#06b6d4", Parameter: "#ec4899",
  Standard: "#3b82f6", Requirement: "#ef4444", Organization: "#84cc16",
  Concept: "#9ca3af",
};

export function SPOForceGraph({ nodes, edges }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef       = useRef<SVGSVGElement>(null);
  const tooltipRef   = useRef<HTMLDivElement>(null);
  const simRef       = useRef<d3.Simulation<SimNode, SimEdge> | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    const svgEl     = svgRef.current;
    if (!container || !svgEl || nodes.length === 0) return;

    simRef.current?.stop();

    function positionTip(ev: MouseEvent, tip: HTMLDivElement) {
      const rect = container!.getBoundingClientRect();
      let x = ev.clientX - rect.left + 14;
      let y = ev.clientY - rect.top - 12;
      if (x + 210 > rect.width) x = ev.clientX - rect.left - 224;
      if (y + 90  > rect.height) y = ev.clientY - rect.top - 90;
      tip.style.left = `${x}px`;
      tip.style.top  = `${y}px`;
    }

    function build(W: number, H: number) {
      const sel = d3.select(svgEl!);
      sel.selectAll("*").remove();
      sel.attr("width", W).attr("height", H);

      const g = sel.append("g");
      sel.call(
        d3.zoom<SVGSVGElement, unknown>()
          .scaleExtent([0.1, 8])
          .on("zoom", e => g.attr("transform", e.transform)),
      );

      sel.append("defs").append("marker")
        .attr("id", "spo-arr").attr("viewBox", "0 -5 10 10")
        .attr("refX", 22).attr("refY", 0)
        .attr("markerWidth", 5).attr("markerHeight", 5)
        .attr("orient", "auto")
        .append("path").attr("d", "M0,-5L10,0L0,5").attr("fill", "#6b7280");

      const simNodes: SimNode[] = nodes.map(n => ({
        ...n,
        x: W / 2 + (Math.random() - 0.5) * Math.min(W, H) * 0.6,
        y: H / 2 + (Math.random() - 0.5) * Math.min(W, H) * 0.6,
      }));

      const nodeSet = new Set(simNodes.map(n => n.node_id));
      const simEdges: SimEdge[] = edges
        .filter(e => nodeSet.has(e.source) && nodeSet.has(e.target))
        .map(e => ({ source: e.source, target: e.target, predicate: e.predicate, predicate_type: e.predicate_type }));

      const showLabels = simEdges.length <= 60;

      const sim = d3.forceSimulation<SimNode>(simNodes)
        .force("link",    d3.forceLink<SimNode, SimEdge>(simEdges)
          .id(d => d.node_id).distance(180).strength(0.4))
        .force("charge",  d3.forceManyBody().strength(-500).distanceMax(600))
        .force("center",  d3.forceCenter(W / 2, H / 2).strength(0.05))
        .force("collide", d3.forceCollide(40))
        .alphaDecay(0.05)
        .velocityDecay(0.4)
        .stop();

      // Pre-compute 150 ticks so the graph appears settled immediately
      for (let i = 0; i < 150; i++) sim.tick();

      simRef.current = sim;

      const link = g.append("g")
        .selectAll<SVGLineElement, SimEdge>("line")
        .data(simEdges).join("line")
        .attr("stroke", "#6b7280").attr("stroke-width", 2).attr("stroke-opacity", 0.7)
        .attr("marker-end", "url(#spo-arr)");

      const edgeLabel = showLabels
        ? g.append("g")
            .selectAll<SVGTextElement, SimEdge>("text")
            .data(simEdges).join("text")
            .text(d => d.predicate.length > 10 ? d.predicate.slice(0, 10) + "…" : d.predicate)
            .attr("fill", "#6b7280").attr("font-size", 9).attr("text-anchor", "middle")
            .attr("pointer-events", "none")
        : null;

      const nodeG = g.append("g")
        .selectAll<SVGGElement, SimNode>("g")
        .data(simNodes).join("g")
        .attr("cursor", "pointer")
        .call(
          d3.drag<SVGGElement, SimNode>()
            .on("start", (ev, d) => { if (!ev.active) sim.alphaTarget(0.2).restart(); d.fx = d.x; d.fy = d.y; })
            .on("drag",  (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
            .on("end",   (ev, d) => { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }),
        );

      nodeG.append("circle")
        .attr("r", 14)
        .attr("fill", d => TYPE_COLOR[d.type] ?? "#6b7280")
        .attr("fill-opacity", 0.9)
        .attr("stroke", "#111827").attr("stroke-width", 1.5);

      nodeG.append("text")
        .text(d => d.name.length > 8 ? d.name.slice(0, 8) + "…" : d.name)
        .attr("dy", 28).attr("text-anchor", "middle")
        .attr("fill", "#d1d5db").attr("font-size", 10)
        .attr("pointer-events", "none");

      // Rich HTML tooltip
      nodeG
        .on("mouseenter", (ev, d) => {
          const tip = tooltipRef.current;
          if (!tip) return;
          const color = TYPE_COLOR[d.type] ?? "#6b7280";
          tip.innerHTML =
            `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">` +
              `<span style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0"></span>` +
              `<span style="font-size:11px;font-weight:600;color:#e5e7eb;word-break:break-all">${d.name}</span>` +
            `</div>` +
            `<div style="font-size:10px;color:#9ca3af">类型：<span style="color:${color}">${d.type}</span></div>` +
            `<div style="font-size:9px;color:#4b5563;margin-top:3px;font-family:monospace;word-break:break-all">${d.node_id}</div>`;
          tip.style.display = "block";
          positionTip(ev.sourceEvent ?? ev, tip);
        })
        .on("mousemove", (ev) => {
          const tip = tooltipRef.current;
          if (tip) positionTip(ev.sourceEvent ?? ev, tip);
        })
        .on("mouseleave", () => {
          const tip = tooltipRef.current;
          if (tip) tip.style.display = "none";
        });

      function tick() {
        link
          .attr("x1", d => (d.source as SimNode).x ?? 0)
          .attr("y1", d => (d.source as SimNode).y ?? 0)
          .attr("x2", d => (d.target as SimNode).x ?? 0)
          .attr("y2", d => (d.target as SimNode).y ?? 0);
        edgeLabel
          ?.attr("x", d => (((d.source as SimNode).x ?? 0) + ((d.target as SimNode).x ?? 0)) / 2)
           .attr("y", d => (((d.source as SimNode).y ?? 0) + ((d.target as SimNode).y ?? 0)) / 2 - 4);
        nodeG.attr("transform", d => `translate(${d.x ?? 0},${d.y ?? 0})`);
      }

      // Render initial pre-computed positions immediately
      tick();

      // Resume at low alpha for fine-tuning (drag responsiveness)
      sim.on("tick", tick).alpha(0.05).restart();
    }

    const ro = new ResizeObserver(entries => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) { ro.disconnect(); build(width, height); }
    });
    ro.observe(container);

    const rect = container.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) { ro.disconnect(); build(rect.width, rect.height); }

    return () => { ro.disconnect(); simRef.current?.stop(); };
  }, [nodes, edges]);

  return (
    <div ref={containerRef} className="w-full h-full relative">
      <svg ref={svgRef} style={{ display: "block", background: "#030712" }} />
      <div
        ref={tooltipRef}
        style={{
          position: "absolute", display: "none", pointerEvents: "none",
          background: "#111827", border: "1px solid #374151", borderRadius: "8px",
          padding: "8px 10px", zIndex: 10, maxWidth: "210px",
          boxShadow: "0 4px 16px rgba(0,0,0,.5)",
        }}
      />
    </div>
  );
}
