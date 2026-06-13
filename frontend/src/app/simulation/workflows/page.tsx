"use client";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

type Workflow = {
  id: string; name: string; description: string; doe_type: string;
  sample_count: number; status: string; total_runs: number;
  completed_runs: number; submit_target: string; created_at: string;
};

const STATUS_COLOR: Record<string, string> = {
  draft:              "bg-gray-800 text-gray-400",
  running:            "bg-blue-900 text-blue-300",
  completed:          "bg-green-900 text-green-300",
  failed:             "bg-red-900 text-red-300",
  results_collected:  "bg-purple-900 text-purple-300",
};

const DOE_CN: Record<string, string> = {
  full_factorial:  "全因子",
  latin_hypercube: "拉丁超立方",
  sobol:           "Sobol 序列",
  adaptive:        "自适应",
};

type NewWF = { name: string; description: string; doe_type: string; sample_count: number; submit_target: string };
const INIT: NewWF = { name: "", description: "", doe_type: "latin_hypercube", sample_count: 10, submit_target: "local" };

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [showNew,   setShowNew]   = useState(false);
  const [form,      setForm]      = useState<NewWF>(INIT);
  const [loading,   setLoading]   = useState(true);
  const [saving,    setSaving]    = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setWorkflows(await fetchApi<Workflow[]>("/api/simulation/workflows"));
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const create = async () => {
    setSaving(true);
    try {
      await fetchApi("/api/simulation/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setShowNew(false); setForm(INIT); load();
    } finally { setSaving(false); }
  };

  const action = async (id: string, act: "submit" | "monitor" | "collect") => {
    await fetchApi(`/api/simulation/workflows/${id}/${act}`, { method: "POST" }).catch(() => {});
    load();
  };

  return (
    <div className="p-6 max-w-5xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">仿真工作流</h1>
          <p className="text-gray-400 text-sm mt-1">参数化扫掠 · DOE 采样 · 集群提交</p>
        </div>
        <button onClick={() => setShowNew(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
          + 新建工作流
        </button>
      </div>

      {/* New workflow form */}
      {showNew && (
        <div className="bg-gray-900 border border-blue-800 rounded-lg p-5 space-y-4">
          <h3 className="text-white font-medium">新建参数化工作流</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-gray-400 text-xs mb-1 block">工作流名称</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div>
              <label className="text-gray-400 text-xs mb-1 block">提交目标</label>
              <select value={form.submit_target} onChange={e => setForm({ ...form, submit_target: e.target.value })}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm">
                <option value="local">本地</option>
                <option value="slurm">Slurm 集群</option>
                <option value="pbs">PBS 集群</option>
              </select>
            </div>
            <div>
              <label className="text-gray-400 text-xs mb-1 block">DOE 策略</label>
              <select value={form.doe_type} onChange={e => setForm({ ...form, doe_type: e.target.value })}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm">
                {Object.entries(DOE_CN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </div>
            <div>
              <label className="text-gray-400 text-xs mb-1 block">样本数量</label>
              <input type="number" min={1} max={500} value={form.sample_count}
                onChange={e => setForm({ ...form, sample_count: parseInt(e.target.value) || 10 })}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
            <div className="col-span-2">
              <label className="text-gray-400 text-xs mb-1 block">描述</label>
              <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm" />
            </div>
          </div>
          <div className="flex gap-3">
            <button onClick={create} disabled={saving || !form.name}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm rounded">
              {saving ? "创建中…" : "创建"}
            </button>
            <button onClick={() => setShowNew(false)}
              className="px-5 py-2 bg-gray-700 text-white text-sm rounded">
              取消
            </button>
          </div>
        </div>
      )}

      {/* Workflow list */}
      {loading ? (
        <div className="space-y-2">{[1,2,3].map(i => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 animate-pulse h-16" />
        ))}</div>
      ) : workflows.length === 0 ? (
        <div className="text-center text-gray-500 py-16">暂无工作流</div>
      ) : (
        <div className="space-y-3">
          {workflows.map(wf => (
            <div key={wf.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-white font-medium">{wf.name}</span>
                  <span className={`ml-3 text-xs px-2 py-0.5 rounded ${STATUS_COLOR[wf.status] ?? "bg-gray-800 text-gray-400"}`}>
                    {wf.status}
                  </span>
                  <p className="text-gray-500 text-xs mt-1">{wf.description}</p>
                </div>
                <div className="flex gap-2 shrink-0">
                  {wf.status === "draft" && (
                    <button onClick={() => action(wf.id, "submit")}
                      className="text-xs px-3 py-1 bg-blue-700 hover:bg-blue-600 text-white rounded">
                      提交
                    </button>
                  )}
                  {wf.status === "running" && (
                    <button onClick={() => action(wf.id, "monitor")}
                      className="text-xs px-3 py-1 bg-gray-700 hover:bg-gray-600 text-white rounded">
                      刷新状态
                    </button>
                  )}
                  {wf.status === "completed" && (
                    <button onClick={() => action(wf.id, "collect")}
                      className="text-xs px-3 py-1 bg-green-700 hover:bg-green-600 text-white rounded">
                      收集结果
                    </button>
                  )}
                </div>
              </div>
              {/* Progress */}
              {wf.total_runs > 0 && (
                <div className="mt-3">
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>{DOE_CN[wf.doe_type] ?? wf.doe_type} · {wf.submit_target}</span>
                    <span>{wf.completed_runs}/{wf.total_runs}</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-1.5">
                    <div className="bg-blue-500 h-1.5 rounded-full transition-all"
                      style={{ width: `${(wf.completed_runs / wf.total_runs) * 100}%` }} />
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
