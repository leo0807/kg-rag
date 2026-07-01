"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Layers, Trash2, RefreshCw, GitBranch } from "lucide-react";
import { SPOForceGraph } from "./SPOForceGraph";
import { SPOGeneratePanel } from "./SPOGeneratePanel";

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

  async function deleteGraph(graphId: string) {
    await fetchApi(`/api/graph/spo/${graphId}`, { method: "DELETE" });
    if (active === graphId) { setActive(null); setGdata(null); }
    await loadList();
  }

  // Auto-select the first graph on initial load
  useEffect(() => {
    if (!initialized.current && graphs.length > 0) {
      initialized.current = true;
      void loadGraph(graphs[0].graph_id);
    }
  }, [graphs]);

  function handleGenerated(graphId: string) {
    loadList().then(() => loadGraph(graphId));
  }

  const meta = gdata?.graph;

  return (
    <div className="flex h-full bg-gray-950">
      {/* Left panel */}
      <aside className="w-72 shrink-0 border-r border-gray-800 flex flex-col gap-4 p-4 overflow-y-auto">
        <div className="flex items-center gap-2">
          <GitBranch size={16} className="text-indigo-400" />
          <span className="text-white text-sm font-semibold">SPO 知识图谱</span>
        </div>

        <SPOGeneratePanel onGenerated={handleGenerated} />

        <div className="space-y-1">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500 uppercase tracking-wider">已生成图谱</span>
            <button onClick={loadList} title="刷新列表">
              <RefreshCw size={12} className="text-gray-500 hover:text-white" />
            </button>
          </div>
          {graphs.length === 0 && (
            <p className="text-xs text-gray-600 py-2 text-center">暂无图谱，请先生成</p>
          )}
          {graphs.map(g => (
            <div key={g.graph_id}
              className={`w-full px-3 py-2 rounded-lg transition-colors flex items-start justify-between gap-2 cursor-pointer ${
                active === g.graph_id ? "bg-indigo-900/40 border border-indigo-700" : "hover:bg-gray-800 border border-transparent"
              }`}
              onClick={() => loadGraph(g.graph_id)}
              role="button" tabIndex={0}
              onKeyDown={e => e.key === "Enter" && loadGraph(g.graph_id)}>
              <div className="min-w-0">
                <div className="text-xs font-medium text-gray-200 truncate">
                  {g.chapter === "ALL" && g.doc_id === "ALL"
                    ? "全局知识图谱"
                    : g.chapter === "ALL"
                    ? `全文 · ${g.doc_id.slice(0, 16)}`
                    : `第 ${g.chapter} 章 · ${g.doc_id.slice(0, 14)}${g.doc_id.length > 14 ? "…" : ""}`}
                </div>
                <div className="text-[10px] text-gray-500 mt-0.5">
                  {g.node_count ?? "—"} 节点 · {g.edge_count ?? "—"} 边
                </div>
                <div className={`text-[10px] mt-0.5 ${g.status === "ready" ? "text-emerald-400" : g.status === "building" ? "text-amber-400" : "text-red-400"}`}>
                  {g.status}
                </div>
              </div>
              <button
                type="button"
                onClick={e => { e.stopPropagation(); void deleteGraph(g.graph_id); }}
                className="shrink-0 p-1 text-gray-600 hover:text-red-400">
                <Trash2 size={12} />
              </button>
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
              <span className="text-white font-medium">
                {meta.chapter === "ALL" && meta.doc_id === "ALL"
                  ? "全局知识图谱"
                  : meta.chapter === "ALL"
                  ? `全文 · ${meta.doc_id}`
                  : `第 ${meta.chapter} 章`}
              </span>
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
          {!active && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-gray-600">
              <GitBranch size={40} strokeWidth={1} />
              <p className="text-sm">选择或生成一张 SPO 知识图谱</p>
            </div>
          )}
          {active && loading && (
            <div className="absolute inset-0 flex items-center justify-center text-gray-500 text-sm gap-2">
              <RefreshCw size={16} className="animate-spin" /> 加载图谱数据…
            </div>
          )}
          {active && !loading && gdata && gdata.nodes.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-gray-600">
              <GitBranch size={32} strokeWidth={1} />
              <p className="text-sm">该章节未提取到有效三元组</p>
              <p className="text-xs text-gray-700">请在左侧面板选择内容更丰富的章节重新生成（推荐第 6 章）</p>
            </div>
          )}
          {active && !loading && gdata && gdata.nodes.length > 0 && (
            <SPOForceGraph nodes={gdata.nodes} edges={gdata.edges} />
          )}
        </div>
      </main>
    </div>
  );
}
