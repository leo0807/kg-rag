"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchApi, ApiError } from "@/lib/api";

type Report = {
  id: string; name: string; description: string;
  is_public: boolean; created_at: string; owner_id: string;
};

export default function ReportsListPage() {
  const router = useRouter();
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState<string | null>(null);
  const [msg, setMsg]         = useState<string | null>(null);
  const [error, setError]     = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const d = await fetchApi<Report[]>("/api/admin/reports");
      setReports(Array.isArray(d) ? d : []);
    } catch (e) {
      setError(e instanceof ApiError && e.status === 403 ? "无权限访问报表功能" : "加载失败，请刷新重试");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const del = async (id: string) => {
    if (!confirm("确认删除？")) return;
    try { await fetchApi(`/api/admin/reports/${id}`, { method: "DELETE" }); } catch { /* ignore */ }
    await load();
  };

  const run = async (id: string) => {
    setRunning(id);
    try {
      const d = await fetchApi<{ snapshot_id: string }>(`/api/admin/reports/${id}/run`, { method: "POST" });
      setMsg(`报表执行完成，快照 ID: ${d.snapshot_id}`);
      setTimeout(() => setMsg(null), 5000);
    } catch { /* ignore */ } finally {
      setRunning(null);
    }
  };

  const exportReport = async (id: string, fmt: string) => {
    try { await fetchApi(`/api/admin/reports/${id}/export?fmt=${fmt}`, { method: "POST" }); } catch { /* ignore */ }
    setMsg(`正在生成 ${fmt.toUpperCase()} 导出…`);
    setTimeout(() => setMsg(null), 4000);
  };

  return (
    <div className="p-6 max-w-6xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">自定义报表</h1>
          <p className="text-gray-400 text-sm mt-1">创建、执行和导出业务报表</p>
        </div>
        <button
          onClick={() => router.push("/admin/reports/new")}
          className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-1.5 rounded"
        >
          + 新建报表
        </button>
      </div>

      {msg && <div className="bg-blue-900 text-blue-300 text-sm px-4 py-2 rounded">{msg}</div>}

      {loading ? (
        <div className="text-center text-gray-400 py-12">加载中…</div>
      ) : error ? (
        <div className="flex flex-col items-center gap-3 text-center py-16">
          <div className="text-4xl">🔒</div>
          <div className="text-red-400 font-medium">{error}</div>
          <p className="text-gray-500 text-sm">请联系平台管理员获取相应权限</p>
        </div>
      ) : reports.length === 0 ? (
        <div className="text-center text-gray-500 py-16 border border-dashed border-gray-700 rounded-lg">
          <p className="text-sm mb-3">暂无报表</p>
          <button onClick={() => router.push("/admin/reports/new")}
            className="text-blue-400 text-sm hover:underline">创建第一个报表</button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {reports.map(r => (
            <div key={r.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex items-center gap-4">
              <div className="flex-1">
                <h3 className="text-white font-medium">{r.name}</h3>
                {r.description && <p className="text-gray-400 text-sm mt-0.5">{r.description}</p>}
                <p className="text-gray-600 text-xs mt-1">
                  {new Date(r.created_at).toLocaleDateString("zh-CN")}
                  {r.is_public && <span className="ml-2 bg-green-900 text-green-300 text-xs px-1.5 py-0.5 rounded">公开</span>}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => run(r.id)} disabled={running === r.id}
                  className="text-xs text-green-400 hover:underline disabled:opacity-50">
                  {running === r.id ? "执行中…" : "执行"}
                </button>
                <button onClick={() => exportReport(r.id, "pdf")}
                  className="text-xs text-blue-400 hover:underline">PDF</button>
                <button onClick={() => router.push(`/admin/reports/${r.id}/edit`)}
                  className="text-xs text-gray-400 hover:underline">编辑</button>
                <button onClick={() => del(r.id)}
                  className="text-xs text-red-400 hover:underline">删除</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
