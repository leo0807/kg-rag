"use client";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

type GapNode = { id: string; name: string; type: string; reason: string; severity: "low" | "medium" | "high" };
type GapData = {
  isolated_nodes: GapNode[];
  sparse_areas: { area: string; node_count: number; edge_count: number }[];
  high_query_low_content: { query: string; count: number; doc_coverage: number }[];
};

const SEV_COLOR = { low: "text-blue-400", medium: "text-yellow-400", high: "text-red-400" };

export function KnowledgeGaps() {
  const [data, setData] = useState<GapData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<GapData>("/api/analytics/knowledge-gaps")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 text-gray-400 text-sm text-center animate-pulse">分析知识缺口中…</div>;

  const isolated = data?.isolated_nodes ?? [];
  const sparse   = data?.sparse_areas ?? [];
  const highQ    = data?.high_query_low_content ?? [];

  return (
    <div className="space-y-4">
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 className="text-white font-medium text-sm mb-3">孤立节点 ({isolated.length})</h3>
        {isolated.length === 0 ? (
          <p className="text-gray-500 text-xs">✓ 未发现孤立节点</p>
        ) : (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {isolated.map(n => (
              <div key={n.id} className="flex items-start gap-3 text-xs">
                <span className={`mt-0.5 ${SEV_COLOR[n.severity]}`}>●</span>
                <div>
                  <span className="text-white font-medium">{n.name}</span>
                  <span className="text-gray-500 ml-2">{n.type}</span>
                  <p className="text-gray-400 mt-0.5">{n.reason}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 className="text-white font-medium text-sm mb-3">稀疏知识区域 ({sparse.length})</h3>
        {sparse.length === 0 ? (
          <p className="text-gray-500 text-xs">✓ 未发现稀疏区域</p>
        ) : (
          <div className="space-y-2">
            {sparse.map((s, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className="text-gray-300">{s.area}</span>
                <div className="flex gap-3">
                  <span className="text-gray-500">{s.node_count} 节点</span>
                  <span className="text-gray-500">{s.edge_count} 关系</span>
                  <span className={s.edge_count < 5 ? "text-yellow-400" : "text-green-400"}>
                    {s.edge_count < 5 ? "稀疏" : "正常"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 className="text-white font-medium text-sm mb-3">高频查询但内容稀少 ({highQ.length})</h3>
        {highQ.length === 0 ? (
          <p className="text-gray-500 text-xs">✓ 未发现内容缺口</p>
        ) : (
          <div className="space-y-2">
            {highQ.map((q, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className="text-gray-300 truncate max-w-xs">{q.query}</span>
                <div className="flex gap-3 shrink-0">
                  <span className="text-gray-500">{q.count} 次查询</span>
                  <div className="w-16 bg-gray-700 rounded-full h-1.5 mt-0.5">
                    <div className="bg-red-500 h-1.5 rounded-full" style={{ width: `${q.doc_coverage * 100}%` }} />
                  </div>
                  <span className="text-red-400">{Math.round(q.doc_coverage * 100)}%</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
