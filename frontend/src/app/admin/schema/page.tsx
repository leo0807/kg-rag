"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { fetchApi } from "@/lib/api";

interface NodeType {
  type: string;
  count: number;
  color: string;
  properties: string[];
  sample: Record<string, unknown> | null;
}

interface EdgeType {
  type: string;
  count: number;
  from: string;
  to: string;
  description: string;
}

interface SchemaStats {
  node_types: NodeType[];
  edge_types: EdgeType[];
}

// Fixed positions for schema nodes (no physics needed for small graph)
const NODE_POSITIONS: Record<string, { x: number; y: number }> = {
  Document:   { x: 300, y: 120 },
  Section:    { x: 300, y: 260 },
  Image:      { x: 130, y: 370 },
  Table:      { x: 290, y: 390 },
  Tool:       { x: 470, y: 200 },
  Material:   { x: 480, y: 310 },
  Process:    { x: 150, y: 210 },
  Constraint: { x: 460, y: 400 },
};

const MAX_R = 48;
const MIN_R = 14;

function nodeRadius(count: number, maxCount: number): number {
  if (maxCount === 0) return MIN_R;
  return MIN_R + (MAX_R - MIN_R) * Math.sqrt(count / maxCount);
}

export default function SchemaPage() {
  const [schema, setSchema] = useState<SchemaStats | null>(null);
  const [selected, setSelected] = useState<NodeType | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const load = useCallback(async () => {
    try {
      const data = await fetchApi<SchemaStats>("/api/graph/schema-stats");
      setSchema(data);
    } catch {}
  }, []);

  useEffect(() => { load(); }, [load]);

  const nodeMap = Object.fromEntries((schema?.node_types ?? []).map((n) => [n.type, n]));
  const maxCount = Math.max(...(schema?.node_types ?? []).map((n) => n.count), 1);

  // Build edge path between two nodes (straight line, offset for bidirectional)
  function edgePath(from: string, to: string, _idx: number): string {
    const a = NODE_POSITIONS[from];
    const b = NODE_POSITIONS[to];
    if (!a || !b) return "";
    if (from === to) return "";
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    const rA = nodeRadius(nodeMap[from]?.count ?? 0, maxCount);
    const rB = nodeRadius(nodeMap[to]?.count ?? 0, maxCount);
    const sx = a.x + (dx / len) * rA;
    const sy = a.y + (dy / len) * rA;
    const ex = b.x - (dx / len) * rB;
    const ey = b.y - (dy / len) * rB;
    return `M ${sx} ${sy} L ${ex} ${ey}`;
  }

  // Stroke width proportional to count
  function edgeWidth(count: number): number {
    const maxEdge = Math.max(...(schema?.edge_types ?? []).map((e) => e.count), 1);
    return 1 + 3 * (count / maxEdge);
  }

  return (
    <main className="p-6 flex gap-6 h-full">
      {/* SVG Canvas */}
      <div className="flex-1 min-w-0 rounded-xl border overflow-hidden"
           style={{ borderColor: "var(--border)", background: "var(--card-bg)" }}>
        <div className="px-4 py-3 border-b text-sm font-medium"
             style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}>
          知识图谱 Schema
        </div>
        <svg ref={svgRef} width="100%" viewBox="0 0 620 500" className="w-full">
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
              <path d="M0,0 L0,6 L8,3 z" fill="#6b7280" />
            </marker>
          </defs>

          {/* Edges */}
          {schema?.edge_types.filter((e) => e.count > 0 && e.from !== e.to).map((edge, i) => {
            const a = NODE_POSITIONS[edge.from];
            const b = NODE_POSITIONS[edge.to];
            if (!a || !b) return null;
            const d = edgePath(edge.from, edge.to, i);
            if (!d) return null;
            const mx = (a.x + b.x) / 2;
            const my = (a.y + b.y) / 2;
            return (
              <g key={`${edge.type}-${i}`}>
                <path d={d} fill="none" stroke="#6b7280"
                      strokeWidth={edgeWidth(edge.count)}
                      strokeOpacity={0.5}
                      markerEnd="url(#arrow)" />
                <text x={mx} y={my - 4} textAnchor="middle" fontSize="8" fill="#9ca3af">
                  {edge.type}
                </text>
              </g>
            );
          })}

          {/* Nodes */}
          {schema?.node_types.map((node) => {
            const pos = NODE_POSITIONS[node.type];
            if (!pos) return null;
            const r = nodeRadius(node.count, maxCount);
            const isSelected = selected?.type === node.type;
            return (
              <g key={node.type} onClick={() => setSelected(isSelected ? null : node)}
                 style={{ cursor: "pointer" }}>
                <circle cx={pos.x} cy={pos.y} r={r}
                        fill={node.color} fillOpacity={0.85}
                        stroke={isSelected ? "#fff" : node.color}
                        strokeWidth={isSelected ? 3 : 0} />
                <text x={pos.x} y={pos.y} textAnchor="middle"
                      dominantBaseline="middle" fontSize="10"
                      fontWeight="600" fill="#fff">
                  {node.type}
                </text>
                <text x={pos.x} y={pos.y + r + 10} textAnchor="middle"
                      fontSize="9" fill="#9ca3af">
                  {node.count.toLocaleString()}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Right panel */}
      <div className="w-64 flex-shrink-0 space-y-4">
        {/* Node detail */}
        {selected ? (
          <div className="rounded-xl border p-4"
               style={{ borderColor: "var(--border)", background: "var(--card-bg)" }}>
            <div className="flex items-center gap-2 mb-3">
              <span className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{ background: selected.color }} />
              <span className="font-semibold text-sm" style={{ color: "var(--text-primary)" }}>
                {selected.type}
              </span>
              <span className="ml-auto text-xs" style={{ color: "var(--text-muted)" }}>
                {selected.count.toLocaleString()}
              </span>
            </div>
            <div className="text-xs font-medium mb-2" style={{ color: "var(--text-muted)" }}>属性</div>
            <ul className="space-y-1">
              {selected.properties.map((p) => (
                <li key={p} className="text-xs font-mono px-2 py-1 rounded"
                    style={{ background: "var(--border)", color: "var(--text-primary)" }}>
                  {p}
                </li>
              ))}
            </ul>
            {selected.sample && (
              <div className="mt-3">
                <div className="text-xs font-medium mb-1" style={{ color: "var(--text-muted)" }}>示例</div>
                <pre className="text-[10px] overflow-auto rounded p-2 max-h-32"
                     style={{ background: "var(--border)", color: "var(--text-primary)" }}>
                  {JSON.stringify(selected.sample, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border p-4 text-xs text-center"
               style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}>
            点击节点查看属性
          </div>
        )}

        {/* Node counts */}
        <div className="rounded-xl border p-4"
             style={{ borderColor: "var(--border)", background: "var(--card-bg)" }}>
          <div className="text-xs font-medium mb-2" style={{ color: "var(--text-muted)" }}>节点统计</div>
          <ul className="space-y-1.5">
            {schema?.node_types.filter((n) => n.count > 0).map((n) => (
              <li key={n.type} className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: n.color }} />
                <span className="text-xs flex-1 truncate" style={{ color: "var(--text-primary)" }}>
                  {n.type}
                </span>
                <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                  {n.count.toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </main>
  );
}
