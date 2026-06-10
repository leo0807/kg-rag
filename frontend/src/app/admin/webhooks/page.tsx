"use client";
import { useEffect, useState } from "react";

type Webhook = {
  id: string; name: string; url: string;
  events: string[]; is_active: boolean;
  success_count: number; failure_count: number;
  last_triggered_at: string | null; created_at: string;
};

const INPUT = "w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500";
const ALL_EVENTS = [
  "answer.created","feedback.submitted","spec.generated",
  "evaluation.completed","document.uploaded","user.created",
  "quota.exceeded","alert.triggered",
];

function WebhookForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [url,  setUrl]  = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const toggle = (e: string) =>
    setSelected((s) => s.includes(e) ? s.filter((x) => x !== e) : [...s, e]);

  const submit = async () => {
    if (!name || !url || !selected.length) { setMsg("请填写名称、URL 并选择至少一个事件"); return; }
    setSaving(true);
    const res = await fetch("/api/admin/webhooks", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("token")}` },
      body: JSON.stringify({ name, url, events: selected }),
    });
    setSaving(false);
    if (res.ok) { setMsg("创建成功"); onCreated(); setName(""); setUrl(""); setSelected([]); }
    else { const d = await res.json(); setMsg(d.detail ?? "创建失败"); }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-5 space-y-4">
      <h3 className="text-white font-medium text-sm">新建 Webhook</h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1">名称</label>
          <input className={INPUT} value={name} onChange={(e) => setName(e.target.value)} placeholder="我的 Webhook" />
        </div>
        <div>
          <label className="block text-xs text-gray-400 mb-1">回调 URL</label>
          <input className={INPUT} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://your-app.com/webhook" />
        </div>
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-2">订阅事件</label>
        <div className="flex flex-wrap gap-2">
          {ALL_EVENTS.map((e) => (
            <button key={e} onClick={() => toggle(e)}
              className={`text-xs px-2 py-1 rounded border ${selected.includes(e) ? "bg-blue-700 border-blue-600 text-white" : "bg-gray-700 border-gray-600 text-gray-300"}`}>
              {e}
            </button>
          ))}
        </div>
      </div>
      {msg && <p className={`text-xs ${msg.includes("成功") ? "text-green-400" : "text-red-400"}`}>{msg}</p>}
      <button onClick={submit} disabled={saving}
        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded">
        {saving ? "创建中…" : "创建"}
      </button>
    </div>
  );
}

export default function WebhooksPage() {
  const [hooks, setHooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () =>
    fetch("/api/admin/webhooks", { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } })
      .then((r) => r.json()).then(setHooks).finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const del = async (id: string) => {
    await fetch(`/api/admin/webhooks/${id}`, {
      method: "DELETE", headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    });
    setHooks((h) => h.filter((x) => x.id !== id));
  };

  const test = async (id: string) => {
    const r = await fetch(`/api/admin/webhooks/${id}/test`, {
      method: "POST", headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    });
    const d = await r.json();
    alert(d.message);
  };

  const toggle = async (wh: Webhook) => {
    await fetch(`/api/admin/webhooks/${wh.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("token")}` },
      body: JSON.stringify({ is_active: !wh.is_active }),
    });
    setHooks((h) => h.map((x) => x.id === wh.id ? { ...x, is_active: !x.is_active } : x));
  };

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Webhook 管理</h1>
        <p className="text-gray-400 text-sm mt-1">订阅系统事件，实时推送到外部系统</p>
      </div>

      <WebhookForm onCreated={load} />

      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        {loading ? <div className="p-8 text-gray-400 text-sm">加载中…</div> : (
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 text-xs">
              <tr>{["名称","URL","事件","成功/失败","状态","操作"].map((h) => (
                <th key={h} className="text-left px-4 py-3">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {hooks.map((wh) => (
                <tr key={wh.id} className="border-t border-gray-800">
                  <td className="px-4 py-3 text-white">{wh.name}</td>
                  <td className="px-4 py-3 text-gray-400 font-mono text-xs truncate max-w-40">{wh.url}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {wh.events.map((e) => (
                        <span key={e} className="text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">{e}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-400">
                    <span className="text-green-400">{wh.success_count}</span>
                    {" / "}
                    <span className="text-red-400">{wh.failure_count}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs ${wh.is_active ? "text-green-400" : "text-gray-500"}`}>
                      {wh.is_active ? "启用" : "停用"}
                    </span>
                  </td>
                  <td className="px-4 py-3 space-x-2">
                    <button onClick={() => test(wh.id)} className="text-xs text-blue-400 hover:underline">测试</button>
                    <button onClick={() => toggle(wh)} className="text-xs text-yellow-400 hover:underline">
                      {wh.is_active ? "停用" : "启用"}
                    </button>
                    <button onClick={() => del(wh.id)} className="text-xs text-red-400 hover:underline">删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && hooks.length === 0 && (
          <div className="text-center text-gray-500 py-12 text-sm">暂无 Webhook</div>
        )}
      </div>
    </div>
  );
}
