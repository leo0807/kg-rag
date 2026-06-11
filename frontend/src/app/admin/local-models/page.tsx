"use client";
import { useEffect, useState } from "react";

type Model = {
  id: string; name: string; version: string; backend: string;
  description: string; parameters_b: number | null; quantization: string;
  context_length: number | null; gpu_memory_required_gb: number | null;
  is_loaded: boolean; live_loaded: boolean; load_time: number | null;
  use_cases: string[]; benchmark_metrics: Record<string, unknown>;
};

type Routes = Record<string, { name: string; backend: string; api_url: string }>;

const INPUT = "w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500";
const BADGE = (on: boolean) => `text-xs px-1.5 py-0.5 rounded ${on ? "bg-green-900 text-green-300" : "bg-gray-700 text-gray-400"}`;

const AUTH = () => `Bearer ${localStorage.getItem("token")}`;

export default function LocalModelsPage() {
  const [models, setModels]     = useState<Model[]>([]);
  const [routes, setRoutes]     = useState<Routes>({});
  const [status, setStatus]     = useState<Record<string, unknown>>({});
  const [loading, setLoading]   = useState(true);
  const [acting, setActing]     = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm]         = useState({ name: "", backend: "ollama", version: "latest", use_cases: "qa", gpu_memory_required_gb: "" });

  const load = async () => {
    setLoading(true);
    const [m, r, s] = await Promise.all([
      fetch("/api/admin/local-models", { headers: { Authorization: AUTH() } }).then(x => x.json()),
      fetch("/api/admin/local-models/routes", { headers: { Authorization: AUTH() } }).then(x => x.json()),
      fetch("/api/admin/local-models/status", { headers: { Authorization: AUTH() } }).then(x => x.json()),
    ]);
    setModels(Array.isArray(m) ? m : []);
    setRoutes(r || {});
    setStatus(s || {});
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const act = async (id: string, action: "load" | "unload" | "benchmark") => {
    setActing(`${id}:${action}`);
    await fetch(`/api/admin/local-models/${id}/${action}`, {
      method: "POST", headers: { Authorization: AUTH() },
    });
    setActing(null);
    await load();
  };

  const create = async () => {
    setActing("create");
    await fetch("/api/admin/local-models", {
      method: "POST",
      headers: { Authorization: AUTH(), "Content-Type": "application/json" },
      body: JSON.stringify({
        ...form,
        use_cases: form.use_cases.split(",").map(s => s.trim()),
        gpu_memory_required_gb: form.gpu_memory_required_gb ? parseFloat(form.gpu_memory_required_gb) : null,
      }),
    });
    setActing(null); setShowForm(false);
    await load();
  };

  const del = async (id: string) => {
    await fetch(`/api/admin/local-models/${id}`, { method: "DELETE", headers: { Authorization: AUTH() } });
    await load();
  };

  return (
    <div className="p-6 max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">本地模型管理</h1>
          <p className="text-gray-400 text-sm mt-1">管理离线 / 私有化部署的本地 AI 模型</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-1.5 rounded">
          + 注册模型
        </button>
      </div>

      {/* Status bar */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "已注册", value: models.length },
          { label: "已加载", value: models.filter(m => m.live_loaded).length },
          { label: "后端可达", value: status.ollama_reachable ? "✓ 在线" : "✗ 离线" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-gray-400 text-xs">{label}</p>
            <p className="text-white text-2xl font-semibold mt-1">{String(value)}</p>
          </div>
        ))}
      </div>

      {/* Register form */}
      {showForm && (
        <div className="bg-gray-800 rounded-lg p-5 space-y-3">
          <h3 className="text-white font-medium text-sm">注册新模型</h3>
          <div className="grid grid-cols-3 gap-3">
            {[
              { k: "name", label: "模型名称", ph: "qwen2.5:72b" },
              { k: "version", label: "版本", ph: "latest" },
              { k: "backend", label: "Backend", ph: "ollama" },
              { k: "use_cases", label: "用途（逗号分隔）", ph: "qa,vision" },
              { k: "gpu_memory_required_gb", label: "显存需求(GB)", ph: "48" },
            ].map(({ k, label, ph }) => (
              <div key={k}>
                <label className="block text-xs text-gray-400 mb-1">{label}</label>
                <input className={INPUT} value={(form as Record<string,string>)[k]} onChange={e => setForm(f => ({ ...f, [k]: e.target.value }))} placeholder={ph} />
              </div>
            ))}
          </div>
          <button onClick={create} disabled={!form.name || acting === "create"}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded">
            {acting === "create" ? "注册中…" : "注册"}
          </button>
        </div>
      )}

      {/* Model table */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        {loading ? <div className="p-8 text-gray-400 text-sm text-center">加载中…</div> : (
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 text-xs">
              <tr>{["名称","后端","规格","用途","状态","性能","操作"].map(h => (
                <th key={h} className="text-left px-4 py-3">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {models.map(m => (
                <tr key={m.id} className="border-t border-gray-800">
                  <td className="px-4 py-3 text-white font-medium">{m.name}<br/><span className="text-gray-500 text-xs">{m.version}</span></td>
                  <td className="px-4 py-3 text-gray-400 text-xs uppercase">{m.backend}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {m.parameters_b && <span>{m.parameters_b}B·</span>}
                    {m.quantization}<br/>
                    {m.gpu_memory_required_gb && <span className="text-yellow-400">{m.gpu_memory_required_gb}GB显存</span>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">{(m.use_cases || []).map(u => (
                      <span key={u} className="text-xs bg-blue-900 text-blue-300 px-1.5 py-0.5 rounded">{u}</span>
                    ))}</div>
                  </td>
                  <td className="px-4 py-3"><span className={BADGE(m.live_loaded)}>{m.live_loaded ? "运行中" : "未加载"}</span></td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {m.benchmark_metrics && Object.keys(m.benchmark_metrics).length > 0 ? (
                      <span>{String((m.benchmark_metrics as Record<string, unknown>).tokens_per_second ?? "—")} tok/s</span>
                    ) : "—"}
                  </td>
                  <td className="px-4 py-3 space-x-2 whitespace-nowrap">
                    {!m.live_loaded ? (
                      <button onClick={() => act(m.id, "load")} disabled={acting === `${m.id}:load`}
                        className="text-xs text-green-400 hover:underline disabled:opacity-50">加载</button>
                    ) : (
                      <button onClick={() => act(m.id, "unload")} disabled={acting === `${m.id}:unload`}
                        className="text-xs text-yellow-400 hover:underline disabled:opacity-50">卸载</button>
                    )}
                    <button onClick={() => act(m.id, "benchmark")} disabled={acting === `${m.id}:benchmark`}
                      className="text-xs text-blue-400 hover:underline disabled:opacity-50">基准</button>
                    <button onClick={() => del(m.id)} className="text-xs text-red-400 hover:underline">删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && models.length === 0 && (
          <div className="text-center text-gray-500 py-12 text-sm">暂无注册模型，点击「注册模型」添加</div>
        )}
      </div>

      {/* Route config */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 className="text-white font-medium text-sm mb-3">模型路由配置</h3>
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(routes).map(([useCase, spec]) => (
            <div key={useCase} className="bg-gray-800 rounded p-3">
              <p className="text-gray-400 text-xs mb-1">{useCase.toUpperCase()}</p>
              <p className="text-white text-sm font-medium">{spec.name}</p>
              <p className="text-gray-500 text-xs">{spec.backend} · {spec.api_url}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
