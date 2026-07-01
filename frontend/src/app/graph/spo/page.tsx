"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Layers, RefreshCw, GitBranch } from "lucide-react";
import { SPOForceGraph } from "./SPOForceGraph";

interface KGMeta {
  graph_id: string; doc_id: string; chapter: string;
  created_at: number; status: string;
  node_count?: number; edge_count?: number;
}
interface SPONode  { node_id: string; name: string; type: string; graph_id: string }
interface SPOEdge  { source: string; target: string; predicate: string; predicate_type: string }
interface GraphData { nodes: SPONode[]; edges: SPOEdge[]; graph: KGMeta | null }

const TYPE_COLOR: Record<string, string> = {
  System: "#6366f1", Component: "#8b5cf6", Process: "#10b981",
  Material: "#f59e0b", Tool: "#06b6d4", Parameter: "#ec4899",
  Standard: "#3b82f6", Requirement: "#ef4444", Organization: "#84cc16", Concept: "#9ca3af",
};

function graphLabel(g: KGMeta) {
  if (g.chapter === "ALL" && g.doc_id === "ALL") return "全局知识图谱";
  if (g.chapter === "ALL") return `全文 · ${g.doc_id.slice(0, 16)}`;
  return `第 ${g.chapter} 章 · ${g.doc_id.slice(0, 14)}${g.doc_id.length > 14 ? "…" : ""}`;
}

export default function SPOGraphPage() {
  const [graphs,  setGraphs]  = useState<KGMeta[]>([]);
  const [active,  setActive]  = useState<string | null>(null);
  const [gdata,   setGdata]   = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);

  const initialized = useRef(false);

  const loadList = useCallback(async () => {
    try { setGraphs(await fetchApi<KGMeta[]>("/api/graph/spo/list")); } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  async function loadGraph(graphId: string) {
    setActive(graphId);
    setLoading(true);
    try {
      const d = await fetchApi<GraphData>(`/api/graph/spo/${graphId}`);
      setGdata(d);
    } finally { setLoading(false); }
  }

  useEffect(() => {
    if (!initialized.current && graphs.length > 0) {
      initialized.current = true;
      void loadGraph(graphs[0].graph_id);
    }
  }, [graphs]);

  const meta = gdata?.graph;

  return (
    <div className="flex h-full bg-gray-950">
      {/* Left panel */}
      <aside className="w-64 shrink-0 border-r border-gray-800 flex flex-col gap-4 p-4 overflow-y-auto">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitBranch size={16} className="text-indigo-400" />
            <span className="text-white text-sm font-semibold">SPO 知识图谱</span>
          </div>
          <button onClick={loadList} title="刷新列表" className="text-gray-500 hover:text-white transition-colors">
            <RefreshCw size={12} />
          </button>
        </div>

        <div className="space-y-1">
          <p className="text-[10px] text-gray-600 uppercase tracking-wider mb-2">已生成图谱</p>
          {graphs.length === 0 && (
            <p className="text-xs text-gray-600 py-4 text-center">暂无图谱数据</p>
          )}
          {graphs.map(g => (
            <div key={g.graph_id}
              className={`w-full px-3 py-2.5 rounded-lg transition-colors cursor-pointer border ${
                active === g.graph_id
                  ? "bg-indigo-900/40 border-indigo-700"
                  : "hover:bg-gray-800 border-transparent"
              }`}
              onClick={() => loadGraph(g.graph_id)}
              role="button" tabIndex={0}
              onKeyDown={e => e.key === "Enter" && loadGraph(g.graph_id)}>
              <div className="text-xs font-medium text-gray-200 truncate">{graphLabel(g)}</div>
              <div className="text-[10px] text-gray-500 mt-0.5">
                {g.node_count ?? "—"} 节点 · {g.edge_count ?? "—"} 边
              </div>
              <div className={`text-[10px] mt-0.5 ${
                g.status === "ready" ? "text-emerald-400"
                : g.status === "building" ? "text-amber-400"
                : "text-red-400"
              }`}>{g.status}</div>
            </div>
          ))}
        </div>

        {/* Legend */}
        {gdata && gdata.nodes.length > 0 && (
          <div className="mt-auto space-y-1 pt-3 border-t border-gray-800">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1">节点类型</p>
            {Object.entries(TYPE_COLOR).filter(([t]) =>
              gdata.nodes.some(n => n.type === t)
            ).map(([t, c]) => (
              <div key={t} className="flex items-center gap-2 text-xs text-gray-400">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: c }} />
                {t}
              </div>
            ))}
          </div>
        )}
      </aside>

      {/* Main area */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Stats bar */}
        {meta && (
          <div className="flex items-center gap-6 px-5 py-2 border-b border-gray-800 bg-gray-900/60">
            <span className="text-xs text-gray-400">
              <span className="text-white font-medium">{graphLabel(meta)}</span>
              {!(meta.chapter === "ALL" && meta.doc_id === "ALL") && (
                <><span className="mx-1 text-gray-600">·</span>{meta.doc_id}</>
              )}
            </span>
            <div className="flex items-center gap-1 text-indigo-400">
              <Layers size={12} />
              <span className="text-xs font-medium">{gdata?.nodes.length ?? 0} 节点</span>
            </div>
            <span className="text-xs text-gray-500">{gdata?.edges.length ?? 0} 关系</span>
          </div>
        )}

        {/* Graph canvas */}
        <div className="flex-1 relative">
          {/* Empty / no-selection state */}
          {!active && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-gray-600">
              <GitBranch size={40} strokeWidth={1} />
              <p className="text-sm">从左侧选择一张知识图谱</p>
            </div>
          )}

          {/* Graph — stays mounted during loading so old graph is visible underneath */}
          {gdata && gdata.nodes.length > 0 && (
            <div className={`absolute inset-0 transition-opacity duration-300 ${loading ? "opacity-25 pointer-events-none" : "opacity-100"}`}>
              <SPOForceGraph nodes={gdata.nodes} edges={gdata.edges} />
            </div>
          )}

          {/* Empty graph state */}
          {active && !loading && gdata && gdata.nodes.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-gray-600">
              <GitBranch size={32} strokeWidth={1} />
              <p className="text-sm">该图谱暂无节点数据</p>
            </div>
          )}

          {/* Loading overlay — shown on top of (dimmed) previous graph */}
          {active && loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-5 bg-gray-950/50 backdrop-blur-sm">
              <div className="relative flex h-16 w-16 items-center justify-center">
                <span className="absolute h-16 w-16 animate-ping rounded-full bg-indigo-500/20" />
                <span className="absolute h-10 w-10 animate-ping rounded-full bg-indigo-500/25" style={{ animationDelay: "250ms" }} />
                <span className="h-6 w-6 rounded-full border-2 border-indigo-500/40 border-t-indigo-400 animate-spin" />
              </div>
              <p className="text-sm text-gray-400">加载图谱数据…</p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
