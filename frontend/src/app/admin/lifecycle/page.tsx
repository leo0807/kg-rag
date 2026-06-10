"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { Clock, Play, CheckCircle } from "lucide-react";

type Policy = {
  id: string; resource_type: string; retention_days: number;
  archive_before_delete: boolean; is_active: boolean;
  last_run_at: string | null; last_run_deleted: number | null;
};

const RESOURCE_LABELS: Record<string, string> = {
  audit_event:   "审计日志",
  query_session: "查询会话",
  query_log:     "查询记录",
  temp_export:   "临时导出",
};

export default function LifecyclePage() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<Record<string, number> | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editVals, setEditVals] = useState({ retention_days: 30, is_active: true, archive_before_delete: false });

  const load = useCallback(async () => {
    setLoading(true);
    const d = await fetchApi<Policy[]>("/api/admin/lifecycle/policies");
    if (d) setPolicies(d);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const startEdit = (p: Policy) => {
    setEditing(p.id);
    setEditVals({ retention_days: p.retention_days, is_active: p.is_active, archive_before_delete: p.archive_before_delete });
  };

  const saveEdit = async (id: string) => {
    await fetchApi(`/api/admin/lifecycle/policies/${id}`, {
      method: "PUT", body: JSON.stringify(editVals),
    });
    setEditing(null);
    await load();
  };

  const triggerRun = async () => {
    setRunning(true);
    setRunResult(null);
    const d = await fetchApi<{ results: Record<string, number> }>("/api/admin/lifecycle/run", { method: "POST" });
    if (d) setRunResult(d.results);
    setRunning(false);
    await load();
  };

  return (
    <div className="flex-1 overflow-y-auto bg-gray-950 p-5 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white flex items-center gap-2">
            <Clock size={20} className="text-blue-400" /> 数据生命周期
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">留存策略管理与定时清理</p>
        </div>
        <button onClick={triggerRun} disabled={running}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-500 disabled:opacity-50">
          <Play size={14} /> {running ? "执行中…" : "立即执行"}
        </button>
      </div>

      {runResult && (
        <div className="bg-green-900/20 border border-green-700/30 rounded-lg p-4">
          <p className="text-sm font-medium text-green-400 flex items-center gap-1.5 mb-2">
            <CheckCircle size={14} /> 执行完成
          </p>
          <div className="flex flex-wrap gap-3">
            {Object.entries(runResult).map(([k, v]) => (
              <span key={k} className="text-xs text-gray-300">
                {RESOURCE_LABELS[k] ?? k}: <span className="text-white font-medium">{v} 条</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {loading ? <p className="text-sm text-gray-500">加载中…</p> : (
        <div className="space-y-3">
          {policies.map((p) => (
            <div key={p.id} className="bg-gray-900 rounded-lg p-4 border border-gray-800">
              {editing === p.id ? (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-white">{RESOURCE_LABELS[p.resource_type] ?? p.resource_type}</p>
                  <div className="flex flex-wrap gap-4">
                    <label className="flex items-center gap-2 text-xs text-gray-400">
                      保留天数
                      <input type="number" min={1} value={editVals.retention_days}
                        onChange={(e) => setEditVals((v) => ({ ...v, retention_days: Number(e.target.value) }))}
                        className="w-20 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-white" />
                    </label>
                    <label className="flex items-center gap-2 text-xs text-gray-400">
                      <input type="checkbox" checked={editVals.is_active}
                        onChange={(e) => setEditVals((v) => ({ ...v, is_active: e.target.checked }))} />
                      启用
                    </label>
                    <label className="flex items-center gap-2 text-xs text-gray-400">
                      <input type="checkbox" checked={editVals.archive_before_delete}
                        onChange={(e) => setEditVals((v) => ({ ...v, archive_before_delete: e.target.checked }))} />
                      删前归档
                    </label>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => saveEdit(p.id)} className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-500">保存</button>
                    <button onClick={() => setEditing(null)} className="px-3 py-1 text-xs text-gray-400 hover:text-white">取消</button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-white">{RESOURCE_LABELS[p.resource_type] ?? p.resource_type}</p>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${p.is_active ? "bg-green-500/15 text-green-400" : "bg-gray-700 text-gray-400"}`}>
                        {p.is_active ? "启用" : "停用"}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">
                      保留 {p.retention_days} 天
                      {p.archive_before_delete && " · 删前归档"}
                      {p.last_run_at && ` · 上次运行: ${new Date(p.last_run_at).toLocaleString("zh-CN")}`}
                      {p.last_run_deleted != null && ` (删除 ${p.last_run_deleted} 条)`}
                    </p>
                  </div>
                  <button onClick={() => startEdit(p)} className="text-xs text-gray-400 hover:text-blue-400">编辑</button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
