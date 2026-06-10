"use client";
import { useEffect, useState } from "react";

type Integration = {
  id: string; name: string; type: string;
  endpoint: string | null; auth_type: string | null;
  status: string; last_error: string | null; created_at: string;
};

const TYPE_OPTIONS = ["plm", "mes", "erp", "custom"];
const AUTH_OPTIONS = ["api_key", "oauth2", "basic", "jwt"];
const STATUS_COLOR: Record<string, string> = {
  active: "text-green-400", inactive: "text-gray-400", error: "text-red-400",
};

const INPUT = "w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500";

function IntegrationForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm] = useState({ name: "", type: "plm", endpoint: "", auth_type: "api_key", auth_config: "{}" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    let auth_config: Record<string, unknown> = {};
    try { auth_config = JSON.parse(form.auth_config); } catch { setMsg("auth_config 不是合法 JSON"); return; }
    setSaving(true);
    const res = await fetch("/api/admin/integrations", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("token")}` },
      body: JSON.stringify({ ...form, auth_config }),
    });
    setSaving(false);
    if (res.ok) { setMsg("创建成功"); onCreated(); }
    else { const d = await res.json(); setMsg(d.detail ?? "创建失败"); }
  };

  return (
    <div className="bg-gray-800 rounded-lg p-5 space-y-4">
      <h3 className="text-white font-medium text-sm">新建集成</h3>
      <div className="grid grid-cols-2 gap-4">
        <div><label className="block text-xs text-gray-400 mb-1">名称</label>
          <input className={INPUT} value={form.name} onChange={set("name")} placeholder="我的 PLM" /></div>
        <div><label className="block text-xs text-gray-400 mb-1">类型</label>
          <select className={INPUT} value={form.type} onChange={set("type")}>
            {TYPE_OPTIONS.map((t) => <option key={t} value={t}>{t.toUpperCase()}</option>)}
          </select></div>
        <div><label className="block text-xs text-gray-400 mb-1">Endpoint URL</label>
          <input className={INPUT} value={form.endpoint} onChange={set("endpoint")} placeholder="https://plm.company.com" /></div>
        <div><label className="block text-xs text-gray-400 mb-1">认证方式</label>
          <select className={INPUT} value={form.auth_type} onChange={set("auth_type")}>
            {AUTH_OPTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select></div>
      </div>
      <div>
        <label className="block text-xs text-gray-400 mb-1">认证配置（JSON，密钥字段建议加密后填写）</label>
        <textarea className={`${INPUT} h-24 font-mono text-xs`} value={form.auth_config} onChange={set("auth_config")} />
      </div>
      {msg && <p className={`text-xs ${msg.includes("成功") ? "text-green-400" : "text-red-400"}`}>{msg}</p>}
      <button onClick={submit} disabled={saving || !form.name}
        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded">
        {saving ? "创建中…" : "创建"}
      </button>
    </div>
  );
}

export default function IntegrationsPage() {
  const [items, setItems] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState<string | null>(null);

  const load = () =>
    fetch("/api/admin/integrations", { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } })
      .then((r) => r.json()).then(setItems).finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const test = async (id: string) => {
    setTesting(id);
    const r = await fetch(`/api/admin/integrations/${id}/test`, {
      method: "POST", headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    });
    const d = await r.json();
    setTesting(null);
    setItems((prev) => prev.map((i) => i.id === id ? { ...i, status: d.status ?? i.status, last_error: d.error ?? null } : i));
  };

  const del = async (id: string) => {
    await fetch(`/api/admin/integrations/${id}`, { method: "DELETE", headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });
    setItems((i) => i.filter((x) => x.id !== id));
  };

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">外部系统集成</h1>
        <p className="text-gray-400 text-sm mt-1">对接 PLM / MES / ERP 等企业系统</p>
      </div>
      <IntegrationForm onCreated={load} />
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        {loading ? <div className="p-8 text-gray-400 text-sm">加载中…</div> : (
          <table className="w-full text-sm">
            <thead className="bg-gray-800 text-gray-400 text-xs">
              <tr>{["名称","类型","Endpoint","认证","状态","操作"].map((h) => (
                <th key={h} className="text-left px-4 py-3">{h}</th>
              ))}</tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} className="border-t border-gray-800">
                  <td className="px-4 py-3 text-white">{i.name}</td>
                  <td className="px-4 py-3 text-gray-400 uppercase text-xs">{i.type}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs truncate max-w-40">{i.endpoint ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{i.auth_type ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs ${STATUS_COLOR[i.status] ?? "text-gray-400"}`}>{i.status}</span>
                    {i.last_error && <p className="text-red-400 text-xs mt-0.5 truncate max-w-32" title={i.last_error}>{i.last_error}</p>}
                  </td>
                  <td className="px-4 py-3 space-x-2">
                    <button onClick={() => test(i.id)} disabled={testing === i.id}
                      className="text-xs text-blue-400 hover:underline disabled:opacity-50">
                      {testing === i.id ? "测试中…" : "测试"}
                    </button>
                    <button onClick={() => del(i.id)} className="text-xs text-red-400 hover:underline">删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && items.length === 0 && (
          <div className="text-center text-gray-500 py-12 text-sm">暂无集成配置</div>
        )}
      </div>
    </div>
  );
}
