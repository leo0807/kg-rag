"use client";

import Link from "next/link";
import { useState, useEffect, useCallback, useRef } from "react";
import { fetchApi, getApiBaseUrl, getAuthHeaders } from "@/lib/api";

type Dataset = {
  id: string; name: string; version: string; description: string;
  total_count: number; type_distribution: Record<string, number>;
  difficulty_distribution: Record<string, number>; created_at: string;
};

export default function EvalDatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1.0");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchApi<Dataset[]>("/api/admin/eval/datasets");
      setDatasets(data ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file || !name.trim()) { setError("请填写名称并选择文件"); return; }
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("name", name);
      form.append("version", version);
      const res = await fetch(`${getApiBaseUrl()}/api/admin/eval/datasets`, {
        method: "POST",
        headers: await getAuthHeaders(),
        body: form,
      });
      if (!res.ok) { const d = await res.json(); setError(d.detail ?? "上传失败"); return; }
      setShowForm(false);
      setName(""); setVersion("1.0");
      if (fileRef.current) fileRef.current.value = "";
      await load();
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string, dsName: string) => {
    if (!confirm(`确认删除数据集「${dsName}」？此操作不可恢复。`)) return;
    await fetchApi(`/api/admin/eval/datasets/${id}`, { method: "DELETE" });
    await load();
  };

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/admin/eval" className="text-gray-400 hover:text-gray-200 text-sm">← 评测中心</Link>
          <h1 className="text-xl font-semibold text-white">数据集管理</h1>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-500">
          + 导入数据集
        </button>
      </div>

      {showForm && (
        <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 space-y-3">
          <h2 className="text-sm font-medium text-gray-200">导入新数据集</h2>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-400 block mb-1">数据集名称 *</label>
              <input value={name} onChange={(e) => setName(e.target.value)}
                placeholder="CPS1000 客观题集" className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">版本号</label>
              <input value={version} onChange={(e) => setVersion(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white" />
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">文件 (.xlsx / .csv / .json) *</label>
            <input ref={fileRef} type="file" accept=".xlsx,.csv,.json"
              className="text-sm text-gray-300 file:mr-3 file:py-1 file:px-3 file:rounded file:bg-gray-700 file:text-gray-200 file:border-0" />
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <div className="flex gap-2">
            <button onClick={handleUpload} disabled={uploading}
              className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50">
              {uploading ? "上传中…" : "确认导入"}
            </button>
            <button onClick={() => { setShowForm(false); setError(""); }}
              className="px-4 py-1.5 text-sm text-gray-400 border border-gray-700 rounded hover:bg-gray-800">
              取消
            </button>
          </div>
        </div>
      )}

      {loading && <p className="text-gray-400 text-sm">加载中…</p>}

      {datasets.length === 0 && !loading && (
        <div className="text-center py-16 text-gray-500">暂无数据集，请点击「导入数据集」</div>
      )}

      <div className="space-y-3">
        {datasets.map((ds) => (
          <div key={ds.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">{ds.name}</span>
                  <span className="text-xs bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">v{ds.version}</span>
                  <span className="text-xs text-blue-400">{ds.total_count} 题</span>
                </div>
                {ds.description && <p className="text-sm text-gray-400 mt-1">{ds.description}</p>}
                <div className="flex gap-4 mt-2 text-xs text-gray-500">
                  {Object.entries(ds.type_distribution ?? {}).map(([k, v]) => (
                    <span key={k}>{k}: {v}</span>
                  ))}
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                <button onClick={async () => {
                  const res = await fetch(`${getApiBaseUrl()}/api/admin/eval/datasets/${ds.id}/export`, { method: "POST", headers: await getAuthHeaders() });
                  if (res.ok) { const b = await res.blob(); const u = URL.createObjectURL(b); const a = document.createElement("a"); a.href = u; a.download = `dataset_${ds.id}.csv`; a.click(); URL.revokeObjectURL(u); }
                }} className="px-2.5 py-1 text-xs text-gray-400 border border-gray-700 rounded hover:bg-gray-800">
                  导出
                </button>
                <button onClick={() => handleDelete(ds.id, ds.name)}
                  className="px-2.5 py-1 text-xs text-red-400 border border-red-900/50 rounded hover:bg-red-900/20">
                  删除
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-600 mt-2">
              创建于 {new Date(ds.created_at).toLocaleDateString("zh-CN")} · ID: {ds.id}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
