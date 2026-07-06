"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";

interface SPONode { node_id: string; name: string; type: string; graph_id: string }
interface SPOEdge { source: string; target: string; predicate: string; predicate_type: string }
interface Props { nodes: SPONode[]; edges: SPOEdge[]; maxEdgesPerNode?: number }

const TYPE_COLOR: Record<string, string> = {
  System: "#6366f1", Component: "#8b5cf6", Process: "#10b981",
  Material: "#f59e0b", Tool: "#06b6d4", Parameter: "#ec4899",
  Standard: "#3b82f6", Requirement: "#ef4444", Organization: "#84cc16", Concept: "#9ca3af",
};
const PRED_COLOR: Record<string, string> = {
  HAS_PROPERTY: "#6366f1", REQUIRES: "#ef4444", USES: "#10b981", COMPOSED_OF: "#f59e0b",
  CONSTRAINED_BY: "#ec4899", APPLIES_TO: "#06b6d4", PART_OF: "#8b5cf6", RELATED_TO: "#6b7280",
};
const NODE_R = 6;

interface SimNode extends d3.SimulationNodeDatum { node_id: string; name: string; type: string }
interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  predicate: string; predicate_type: string;
}

export function SPOForceGraph({ nodes, edges, maxEdgesPerNode = 10 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || nodes.length === 0) return;
    const el: HTMLCanvasElement = canvas; // narrowed non-null for closures

    // ── Per-node edge cap ──────────────────────────────────────────────────────
    const nodeIds = new Set(nodes.map(n => n.node_id));
    const nodeDeg = new Map<string, number>();
    const keptEdges: SPOEdge[] = [];
    for (const e of edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))) {
      const sc = nodeDeg.get(e.source) ?? 0, tc = nodeDeg.get(e.target) ?? 0;
      if (sc >= maxEdgesPerNode && tc >= maxEdgesPerNode) continue;
      keptEdges.push(e);
      nodeDeg.set(e.source, sc + 1);
      nodeDeg.set(e.target, tc + 1);
    }

    // ── Canvas setup (HiDPI) ──────────────────────────────────────────────────
    const dpr = window.devicePixelRatio ?? 1;
    const W = canvas.offsetWidth, H = canvas.offsetHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);

    // ── Simulation data ────────────────────────────────────────────────────────
    const simNodes: SimNode[] = nodes.map(n => ({ ...n }));
    const nodeById = new Map(simNodes.map(n => [n.node_id, n]));
    const simLinks: SimLink[] = keptEdges.map(e => ({
      source: nodeById.get(e.source) as SimNode,
      target: nodeById.get(e.target) as SimNode,
      predicate: e.predicate,
      predicate_type: e.predicate_type,
    }));

    // ── Zoom state ─────────────────────────────────────────────────────────────
    let tx = 0, ty = 0, tk = 1;

    function draw() {
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.translate(tx, ty);
      ctx.scale(tk, tk);

      // Edges
      ctx.lineWidth = 1 / tk;
      for (const lk of simLinks) {
        const s = lk.source as SimNode, t = lk.target as SimNode;
        if (s.x == null || t.x == null) continue;
        const color = PRED_COLOR[lk.predicate_type] ?? "#6b7280";
        ctx.strokeStyle = color + "88";
        ctx.beginPath();
        ctx.moveTo(s.x!, s.y!);
        ctx.lineTo(t.x!, t.y!);
        ctx.stroke();
      }

      // Nodes
      for (const n of simNodes) {
        if (n.x == null) continue;
        const color = TYPE_COLOR[n.type] ?? "#6b7280";
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(n.x!, n.y!, NODE_R / tk, 0, Math.PI * 2);
        ctx.fill();
      }

      // Labels (only when zoomed in enough)
      if (tk > 0.6) {
        ctx.textBaseline = "middle";
        ctx.font = `${Math.round(10 / tk)}px Inter,sans-serif`;
        for (const n of simNodes) {
          if (n.x == null) continue;
          const color = TYPE_COLOR[n.type] ?? "#6b7280";
          ctx.fillStyle = color + "dd";
          ctx.fillText(n.name, n.x! + NODE_R / tk + 2, n.y!);
        }
      }

      ctx.restore();
    }

    // ── D3 force simulation ────────────────────────────────────────────────────
    // For large graphs (>500 nodes) skip forceManyBody (O(n log n)) and use
    // forceX/Y cluster-by-type (O(n)) so the simulation stays responsive.
    const TYPES = Object.keys(TYPE_COLOR);
    const typeIndex = (t: string) => { const i = TYPES.indexOf(t); return i < 0 ? TYPES.length : i; };
    const typeCount = TYPES.length + 1;
    const large = simNodes.length > 500;

    const sim = d3.forceSimulation<SimNode>(simNodes)
      .force("link", d3.forceLink<SimNode, SimLink>(simLinks)
        .id(d => d.node_id).distance(large ? 120 : 140).strength(0.3))
      .force("charge", large
        ? null
        : d3.forceManyBody<SimNode>().strength(-600).distanceMax(500))
      .force("clusterX", large
        ? d3.forceX<SimNode>(n => {
            const col = typeIndex(n.type) % Math.ceil(Math.sqrt(typeCount));
            return W * 0.1 + col * (W * 0.8 / Math.ceil(Math.sqrt(typeCount)));
          }).strength(0.03)
        : null)
      .force("clusterY", large
        ? d3.forceY<SimNode>(n => {
            const row = Math.floor(typeIndex(n.type) / Math.ceil(Math.sqrt(typeCount)));
            return H * 0.1 + row * (H * 0.8 / Math.ceil(Math.sqrt(typeCount)));
          }).strength(0.03)
        : null)
      .force("center", d3.forceCenter<SimNode>(W / 2, H / 2).strength(large ? 0.003 : 0.02))
      .force("collide", d3.forceCollide<SimNode>(large ? 28 : 40))
      .alphaDecay(large ? 0.03 : 0.02)
      .on("tick", draw);

    // ── Hit test: canvas px → nearest simNode ─────────────────────────────────
    function nodeAt(sx: number, sy: number): SimNode | null {
      const wx = (sx - tx) / tk, wy = (sy - ty) / tk;
      const thr = Math.max(20, NODE_R * 3) / tk;
      let best: SimNode | null = null, bestD = thr;
      for (const n of simNodes) {
        if (n.x == null) continue;
        const d = Math.hypot(n.x - wx, (n.y ?? 0) - wy);
        if (d < bestD) { bestD = d; best = n; }
      }
      return best;
    }

    // ── D3 drag ────────────────────────────────────────────────────────────────
    let dragNode: SimNode | null = null;

    const drag = d3.drag<HTMLCanvasElement, unknown>()
      // Only activate when pointer is over a node; otherwise let zoom pan
      .filter((ev: Event) => {
        const me = ev as MouseEvent;
        return !!nodeAt(me.offsetX, me.offsetY);
      })
      .on("start", (ev: d3.D3DragEvent<HTMLCanvasElement, unknown, unknown>) => {
        const me = ev.sourceEvent as MouseEvent;
        dragNode = nodeAt(me.offsetX, me.offsetY);
        if (!dragNode) return;
        if (!ev.active) sim.alphaTarget(0.3).restart();
        dragNode.fx = dragNode.x;
        dragNode.fy = dragNode.y;
        el.style.cursor = "grabbing";
      })
      .on("drag", (ev: d3.D3DragEvent<HTMLCanvasElement, unknown, unknown>) => {
        if (!dragNode) return;
        const me = ev.sourceEvent as MouseEvent;
        dragNode.fx = (me.offsetX - tx) / tk;
        dragNode.fy = (me.offsetY - ty) / tk;
      })
      .on("end", (ev: d3.D3DragEvent<HTMLCanvasElement, unknown, unknown>) => {
        if (!dragNode) return;
        if (!ev.active) sim.alphaTarget(0);
        dragNode.fx = null;
        dragNode.fy = null;
        dragNode = null;
        el.style.cursor = "grab";
      });

    // ── D3 zoom ────────────────────────────────────────────────────────────────
    const zoom = d3.zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.05, 8])
      .on("zoom", (ev: d3.D3ZoomEvent<HTMLCanvasElement, unknown>) => {
        tx = ev.transform.x; ty = ev.transform.y; tk = ev.transform.k;
        draw();
      });

    // Attach drag first so its filter can stopPropagation before zoom sees the event
    d3.select(canvas).call(drag).call(zoom);

    // ── Tooltip on hover ───────────────────────────────────────────────────────
    function onMouseMove(ev: MouseEvent) {
      if (dragNode) return; // suppress tooltip while dragging
      const n = nodeAt(ev.offsetX, ev.offsetY);
      el.title = n ? `${n.name} [${n.type}]` : "";
      el.style.cursor = n ? "grab" : "default";
    }
    el.addEventListener("mousemove", onMouseMove);

    return () => {
      sim.stop();
      el.removeEventListener("mousemove", onMouseMove);
      d3.select(el).on(".zoom", null).on(".drag", null);
    };
  }, [nodes, edges, maxEdgesPerNode]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: "100%", height: "100%", display: "block", background: "#030712", cursor: "grab" }}
    />
  );
}
