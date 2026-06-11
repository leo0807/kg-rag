"use client";
import { useEffect, useState } from "react";

type Job = {
  id: string; name: string; base_model: string; method: string;
  status: string; progress: number; train_loss: number | null;
  eval_loss: number | null; epochs: int; created_at: string;
  started_at: string | null; completed_at: string | null;
};
type int = number;

const AUTH = () => `Bearer ${typeof window !== "undefined" ? localStorage.getItem("token") : ""}`;
const api = (path: string, opts?: RequestInit) =>
  fetch(`/api/admin/finetune${path}`, { headers: { Authorization: AUTH(), "Content-Type": "application/json" }, ...opts });

const STATUS_COLOR: Record<string, string> = {
  pending:   "bg-gray-700 text-gray-300",
  running:   "bg-blue-900 text-blue-300",
  completed: "bg-green-900 text-green-300",
  failed:    "bg-red-900 text-red-300",
};

const INPUT = "w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500";

export default function FinetunePage() {
  const [jobs, setJobs]     = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing]   = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [msg, setMsg]           = useState<string | null>(null);
  const [form, setForm] = useState({
    name: "", base_model: "qwen2.5:72b", method: "lora",
    epochs: "3", batch_size: "4", learning_rate: "0.0002",
    dataset_path: "", auto_collect: true,
  });

  const load = async () => {
    setLoading(true);
    const r = await api("").then(x => x.json());
    setJobs(Array.isArray(r) ? r : []);
    setLoading(false);
  };

  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t); }, []);

  const create = async () => {
    if (!form.name || !form.base_model) return;
    setActing("create");
    const r = await api("", {
      method: "POST",
      body: JSON.stringify({
        ...form,
        epochs: parseInt(form.epochs),
        batch_size: parseInt(form.batch_size),
        learning_rate: parseFloat(form.learning_rate),
      }),
    });
    if (r.ok) { setShowForm(false); setMsg("任务已创建"); }
    else { const e = await r.json(); setMsg(`创建失败: ${e.detail}`); }
    setActing(null);
    await load();
    setTimeout(() => setMsg(null), 4000);
  };

  const cancel = async (id: string) => {
    setActing(`cancel-${id}`);
    await api(`/${id}/cancel`, { method: "POST" });
    setActing(null); await load();
  };

  const deploy = async (id: string) => {
    if (!confirm("确认部署此模型？将合并 LoRA 权重并注册为本地模型。")) return;
    setActing(`deploy-${id}`);
    const r = await api(`/${id}/deploy`, { method: "POST" });
    if (r.ok) setMsg("模型已部署");
    else { const e = await r.json(); setMsg(`部署失败: ${e.detail}`); }
    setActing(null);
    setTimeout(() => setMsg(null), 5000);
  };

  const fmtDate = (s: string | null) => s ? new Date(s).toLocaleString("zh-CN") : "—";

  return (
    <div className="p-6 max-w-6xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">本地模型微调</h1>
          <p className="text-gray-400 text-sm mt-1">基于用户反馈和评测数据训练专属模型</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-4 py-1.5 rounded">
          + 新建任务
        </button>
      </div>

      {msg && <div className="bg-blue-900 text-blue-300 px-4 py-2 rounded text-sm">{msg}</div>}

      {showForm && (
        <div className="bg-gray-800 rounded-lg p-5 space-y-4">
          <h3 className="text-white font-medium text-sm">新建微调任务</h3>
          <div className="grid grid-cols-3 gap-3">
            {([
              { k: "name",          label: "任务名称",    ph: "my-qa-model" },
              { k: "base_model",    label: "基础模型",    ph: "qwen2.5:72b" },
              { k: "method",        label: "方法",        ph: "lora" },
              { k: "epochs",        label: "训练轮数",    ph: "3" },
              { k: "batch_size",    label: "Batch Size",  ph: "4" },
              { k: "learning_rate", label: "学习率",      ph: "0.0002" },
              { k: "dataset_path",  label: "数据集路径（可空，自动采集）", ph: "/data/train.json" },
            ] as { k: keyof typeof form; label: string; ph: string }[]).map(({ k, label, ph }) => (
              <div key={k} className={k === "dataset_path" ? "col-span-2" : ""}>
                <label className="block text-xs text-gray-400 mb-1">{label}</label>
                <input className={INPUT} value={String(form[k])}
                  onChange={e => setForm(f => ({ ...f, [k]: e.target.value }))} placeholder={ph} />
              </div>
            ))}
            <div className="flex items-center gap-2 pt-5">
              <input type="checkbox" id="ac" checked={form.auto_collect}
                onChange={e => setForm(f => ({ ...f, auto_collect: e.target.checked }))} />
              <label htmlFor="ac" className="text-xs text-gray-300">自动采集反馈数据</label>
            </div>
          </div>
          <button onClick={create} disabled={!form.name || acting === "create"}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded">
            {acting === "create" ? "提交中…" : "开始训练"}
          </button>
        </div>
      )}

      {loading && jobs.length === 0 ? (
        <div className="text-center text-gray-400 py-12 text-sm">加载中…</div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 text-xs">
              <tr>{["任务名称", "基础模型", "方法", "状态", "进度", "Loss", "创建时间", "操作"].map(h => (
                <th key={h} className="text-left px-4 py-3">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {jobs.map(j => (
                <tr key={j.id} className="border-t border-gray-800">
                  <td className="px-4 py-3 text-white font-medium">{j.name}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs font-mono">{j.base_model}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs uppercase">{j.method}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLOR[j.status] || "bg-gray-700 text-gray-300"}`}>
                      {j.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {j.status === "running" ? (
                      <div className="w-24">
                        <div className="bg-gray-700 rounded-full h-1.5">
                          <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${j.progress}%` }} />
                        </div>
                        <span className="text-xs text-gray-400 mt-0.5">{j.progress}%</span>
                      </div>
                    ) : (
                      <span className="text-gray-400 text-xs">{j.progress}%</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">
                    {j.train_loss != null ? j.train_loss.toFixed(4) : "—"}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">{fmtDate(j.created_at)}</td>
                  <td className="px-4 py-3 space-x-2 whitespace-nowrap">
                    {j.status === "running" && (
                      <button onClick={() => cancel(j.id)} disabled={acting === `cancel-${j.id}`}
                        className="text-xs text-yellow-400 hover:underline disabled:opacity-50">取消</button>
                    )}
                    {j.status === "completed" && (
                      <button onClick={() => deploy(j.id)} disabled={acting === `deploy-${j.id}`}
                        className="text-xs text-green-400 hover:underline disabled:opacity-50">部署</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {jobs.length === 0 && (
            <div className="text-center text-gray-500 py-12 text-sm">暂无微调任务</div>
          )}
        </div>
      )}
    </div>
  );
}
