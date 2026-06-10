"use client";

import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { ChevronLeft, ChevronRight } from "lucide-react";

type Tab = "global" | "graph";

// ── Global audit event types ──────────────────────────────────────────────────
type AuditEvent = {
  id: string; event_type: string; action: string;
  user_id: string | null; user_name: string | null; user_role: string | null;
  ip_address: string | null; resource_type: string | null;
  resource_name: string | null; success: boolean;
  error_message: string | null; request_path: string | null;
  request_method: string | null; timestamp: string;
};
type AuditEventDetail = AuditEvent & { trace_id: string | null; before_state: unknown; after_state: unknown; changes: Record<string, unknown> | null; user_agent: string | null };

// ── Legacy graph edit types ───────────────────────────────────────────────────
type GraphEntry  = { id: number; username: string; full_name: string; action: string; resource: string; detail: string; created_at: string };
type GraphResp   = { data: GraphEntry[]; total: number; page: number; pages: number };

const ACTION_COLOR: Record<string, string> = {
  create: "text-green-400", delete: "text-red-400", update: "text-yellow-400",
  read: "text-blue-400", auth: "text-purple-400", export: "text-orange-400",
};
const GRAPH_STYLE: Record<string, string> = {
  node_patch: "bg-blue-500/15 text-blue-400", edge_create: "bg-green-500/15 text-green-400",
  edge_delete: "bg-red-500/15 text-red-400",
};

export default function AuditPage() {
  const [tab, setTab] = useState<Tab>("global");

  // Global audit state
  const [events, setEvents]       = useState<AuditEvent[]>([]);
  const [total, setTotal]         = useState(0);
  const [loading, setLoading]     = useState(false);
  const [selected, setSelected]   = useState<AuditEventDetail | null>(null);
  const [search, setSearch]       = useState("");
  const [evtType, setEvtType]     = useState("");
  const [succFilter, setSuccFilter] = useState("");
  const [page, setPage]           = useState(1);

  // Legacy graph state
  const [gData, setGData]   = useState<GraphEntry[]>([]);
  const [gTotal, setGTotal] = useState(0);
  const [gPages, setGPages] = useState(1);
  const [gPage, setGPage]   = useState(1);
  const [gLoading, setGLoading] = useState(false);

  const loadGlobal = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams({ page: String(page), page_size: "50" });
      if (search) p.set("search", search);
      if (evtType) p.set("event_type", evtType);
      if (succFilter !== "") p.set("success", succFilter);
      const d = await fetchApi<{ total: number; events: AuditEvent[] }>(`/api/admin/audit/events?${p}`);
      setEvents(d?.events ?? []); setTotal(d?.total ?? 0);
    } finally { setLoading(false); }
  }, [page, search, evtType, succFilter]);

  const loadGraph = useCallback(async (p: number) => {
    setGLoading(true);
    try {
      const res = await fetchApi<GraphResp>(`/api/users/audit-logs?page=${p}&per_page=25`);
      setGData(res.data); setGTotal(res.total); setGPages(res.pages); setGPage(p);
    } finally { setGLoading(false); }
  }, []);

  useEffect(() => { if (tab === "global") loadGlobal(); }, [tab, loadGlobal]);
  useEffect(() => { if (tab === "graph") loadGraph(1); }, [tab, loadGraph]);

  const openDetail = async (id: string) => {
    const d = await fetchApi<AuditEventDetail>(`/api/admin/audit/events/${id}`);
    if (d) setSelected(d);
  };

  return (
    <div className="flex-1 overflow-hidden bg-gray-950 flex flex-col">
      <div className="p-5 border-b border-gray-800 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-xl font-semibold text-white">审计日志</h1>
          <p className="text-sm text-gray-400 mt-0.5">合规可追溯 · 不可篡改</p>
        </div>
        {tab === "global" && (
          <a href={`/api/admin/audit/export${evtType ? `?event_type=${evtType}` : ""}`}
            className="px-3 py-1.5 text-sm text-gray-300 border border-gray-700 rounded hover:bg-gray-800">
            导出 CSV
          </a>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-800 px-5 shrink-0">
        {(["global", "graph"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${tab === t ? "border-blue-500 text-white" : "border-transparent text-gray-400 hover:text-gray-200"}`}>
            {t === "global" ? "全局审计" : "图谱编辑"}
          </button>
        ))}
      </div>

      {/* Global audit tab */}
      {tab === "global" && (
        <>
          <div className="p-3 border-b border-gray-800 flex gap-2 shrink-0 flex-wrap">
            <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="路径 / 用户 / 资源" className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-xs text-white w-52" />
            <input value={evtType} onChange={(e) => { setEvtType(e.target.value); setPage(1); }}
              placeholder="事件类型" className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-xs text-white w-36" />
            <select value={succFilter} onChange={(e) => { setSuccFilter(e.target.value); setPage(1); }}
              className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-xs text-white">
              <option value="">全部</option><option value="true">成功</option><option value="false">失败</option>
            </select>
            <button onClick={loadGlobal} disabled={loading}
              className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50">
              {loading ? "…" : "刷新"}
            </button>
            <span className="text-xs text-gray-500 self-center">共 {total} 条</span>
          </div>

          <div className="flex flex-1 overflow-hidden">
            <div className={`overflow-y-auto ${selected ? "w-1/2" : "flex-1"}`}>
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-gray-900">
                  <tr className="text-gray-400 border-b border-gray-800 text-left">
                    <th className="py-2 px-3 font-medium">时间</th>
                    <th className="py-2 px-3 font-medium">事件</th>
                    <th className="py-2 px-3 font-medium">用户</th>
                    <th className="py-2 px-3 font-medium">路径</th>
                    <th className="py-2 px-3 font-medium">结果</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/30">
                  {events.map((e) => (
                    <tr key={e.id} onClick={() => openDetail(e.id)}
                      className={`cursor-pointer hover:bg-gray-800/60 ${selected?.id === e.id ? "bg-gray-800/80" : ""}`}>
                      <td className="py-1.5 px-3 text-gray-500 whitespace-nowrap">
                        {new Date(e.timestamp).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                      </td>
                      <td className={`py-1.5 px-3 font-medium ${ACTION_COLOR[e.action] ?? "text-gray-300"}`}>{e.event_type}</td>
                      <td className="py-1.5 px-3 text-gray-300">{e.user_name ?? "—"}</td>
                      <td className="py-1.5 px-3 text-gray-400 truncate max-w-xs">{e.request_path ?? "—"}</td>
                      <td className="py-1.5 px-3">
                        <span className={`w-2 h-2 rounded-full inline-block ${e.success ? "bg-green-500" : "bg-red-500"}`} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex items-center justify-between p-3 border-t border-gray-800">
                <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
                  className="p-1.5 rounded bg-gray-800 text-gray-400 hover:text-white disabled:opacity-30"><ChevronLeft size={12} /></button>
                <span className="text-xs text-gray-500">第 {page} 页</span>
                <button onClick={() => setPage(page + 1)} disabled={events.length < 50}
                  className="p-1.5 rounded bg-gray-800 text-gray-400 hover:text-white disabled:opacity-30"><ChevronRight size={12} /></button>
              </div>
            </div>
            {selected && (
              <div className="w-1/2 border-l border-gray-800 overflow-y-auto p-4 space-y-2">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-sm font-medium text-white">{selected.event_type}</span>
                  <button onClick={() => setSelected(null)} className="text-gray-500 hover:text-white text-lg">×</button>
                </div>
                {[["时间", new Date(selected.timestamp).toLocaleString("zh-CN")],
                  ["用户", `${selected.user_name ?? "—"} · ${selected.user_role ?? "?"}`],
                  ["IP", selected.ip_address ?? "—"],
                  ["路径", `${selected.request_method} ${selected.request_path}`],
                  ["结果", selected.success ? "✓ 成功" : `✗ ${selected.error_message ?? "失败"}`],
                  ["Trace", selected.trace_id ?? "—"],
                ].map(([k, v]) => (
                  <div key={String(k)} className="text-xs flex gap-2">
                    <span className="text-gray-500 w-14 shrink-0">{k}:</span>
                    <span className="text-gray-300">{String(v)}</span>
                  </div>
                ))}
                {selected.changes && (
                  <pre className="text-xs text-gray-300 bg-gray-900 rounded p-2 overflow-x-auto mt-2">
                    {JSON.stringify(selected.changes, null, 2)}
                  </pre>
                )}
                {selected.user_id && (
                  <Link href={`/admin/audit/users/${selected.user_id}`}
                    className="text-xs text-blue-400 hover:underline block mt-2">
                    查看用户全部活动 →
                  </Link>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* Legacy graph tab */}
      {tab === "graph" && (
        <div className="flex-1 overflow-y-auto p-5">
          <p className="text-xs text-gray-500 mb-4">共 {gTotal} 条图谱编辑记录</p>
          {gLoading ? <p className="text-gray-500 text-sm">加载中…</p> : (
            <table className="w-full text-xs border border-gray-800 rounded-lg overflow-hidden">
              <thead className="bg-gray-900 border-b border-gray-800">
                <tr className="text-left text-gray-500">
                  <th className="px-4 py-2">时间</th><th className="px-4 py-2">操作人</th>
                  <th className="px-4 py-2">类型</th><th className="px-4 py-2">资源</th><th className="px-4 py-2">详情</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {gData.map((e) => (
                  <tr key={e.id} className="hover:bg-gray-900/50">
                    <td className="px-4 py-2 text-gray-500">{new Date(e.created_at).toLocaleString("zh-CN")}</td>
                    <td className="px-4 py-2 text-gray-300">{e.full_name || e.username}</td>
                    <td className="px-4 py-2"><span className={`px-2 py-0.5 rounded text-[11px] ${GRAPH_STYLE[e.action] ?? "bg-gray-700 text-gray-400"}`}>{e.action}</span></td>
                    <td className="px-4 py-2 text-indigo-400 truncate max-w-[120px]">{e.resource}</td>
                    <td className="px-4 py-2 text-gray-500 truncate max-w-xs">{e.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {gPages > 1 && (
            <div className="flex items-center justify-center gap-3 mt-4">
              <button onClick={() => loadGraph(gPage - 1)} disabled={gPage <= 1}
                className="p-1.5 rounded bg-gray-800 text-gray-400 hover:text-white disabled:opacity-30"><ChevronLeft size={13} /></button>
              <span className="text-xs text-gray-500">{gPage} / {gPages}</span>
              <button onClick={() => loadGraph(gPage + 1)} disabled={gPage >= gPages}
                className="p-1.5 rounded bg-gray-800 text-gray-400 hover:text-white disabled:opacity-30"><ChevronRight size={13} /></button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
