"use client";
import { useEffect, useState } from "react";
import { fetchApi, ApiError } from "@/lib/api";
import { Plug, CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp, Link2, RefreshCw } from "lucide-react";

type Integration = {
  id: string; name: string; type: string;
  endpoint: string | null; auth_type: string | null;
  status: string; last_error: string | null; created_at: string;
};

const TYPE_OPTIONS = ["plm", "mes", "erp", "custom"];
const AUTH_OPTIONS = ["api_key", "oauth2", "basic", "jwt"];

const STATUS_BADGE: Record<string, string> = {
  active:   "bg-green-500/10 text-green-400 border-green-500/20",
  inactive: "bg-gray-500/10 text-gray-400 border-gray-700",
  error:    "bg-red-500/10  text-red-400  border-red-500/20",
};
const TYPE_COLOR: Record<string, string> = {
  plm: "text-blue-400", mes: "text-cyan-400", erp: "text-violet-400", custom: "text-amber-400",
};

const INPUT = "w-full bg-gray-800/60 border border-gray-700/60 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/70 transition-colors";

function KpiCard({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: number | string; color: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-4 flex items-center gap-3">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
        <Icon size={16} />
      </div>
      <div>
        <div className="text-xl font-bold text-white tabular-nums">{value}</div>
        <div className="text-xs text-gray-500">{label}</div>
      </div>
    </div>
  );
}

function IntegrationForm({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(true);
  const [form, setForm] = useState({ name: "", type: "plm", endpoint: "", auth_type: "api_key", auth_config: "{}" });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }));

  const submit = async () => {
    let auth_config: Record<string, unknown> = {};
    try { auth_config = JSON.parse(form.auth_config); } catch { setMsg("auth_config 不是合法 JSON"); return; }
    setSaving(true);
    try {
      await fetchApi("/api/admin/integrations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, auth_config }),
      });
      setMsg("创建成功"); onCreated();
    } catch (e) {
      setMsg(e instanceof ApiError ? (e.message || "创建失败") : "创建失败");
    } finally { setSaving(false); }
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <button className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800/50 transition-colors"
              onClick={() => setOpen(o => !o)}>
        <div className="flex items-center gap-2.5">
          <Link2 size={15} className="text-blue-400" />
          <span className="text-sm font-medium text-white">新建集成</span>
        </div>
        {open ? <ChevronUp size={14} className="text-gray-500" /> : <ChevronDown size={14} className="text-gray-500" />}
      </button>

      {open && (
        <div className="px-5 pb-5 border-t border-gray-800 pt-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div><label className="block text-xs text-gray-500 mb-1.5 font-medium">名称</label>
              <input className={INPUT} value={form.name} onChange={set("name")} placeholder="我的 PLM" /></div>
            <div><label className="block text-xs text-gray-500 mb-1.5 font-medium">类型</label>
              <select className={INPUT} value={form.type} onChange={set("type")}>
                {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t.toUpperCase()}</option>)}
              </select></div>
            <div><label className="block text-xs text-gray-500 mb-1.5 font-medium">Endpoint URL</label>
              <input className={INPUT} value={form.endpoint} onChange={set("endpoint")} placeholder="https://plm.company.com" /></div>
            <div><label className="block text-xs text-gray-500 mb-1.5 font-medium">认证方式</label>
              <select className={INPUT} value={form.auth_type} onChange={set("auth_type")}>
                {AUTH_OPTIONS.map(a => <option key={a} value={a}>{a}</option>)}
              </select></div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1.5 font-medium">认证配置（JSON）</label>
            <textarea className={`${INPUT} h-20 font-mono text-xs resize-none`} value={form.auth_config} onChange={set("auth_config")} />
          </div>
          {msg && <p className={`text-xs ${msg.includes("成功") ? "text-green-400" : "text-red-400"}`}>{msg}</p>}
          <button onClick={submit} disabled={saving || !form.name}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg font-medium transition-colors">
            {saving ? "创建中…" : "创建集成"}
          </button>
        </div>
      )}
    </div>
  );
}

export default function IntegrationsPage() {
  const [items, setItems] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    fetchApi<Integration[]>("/api/admin/integrations")
      .then(d => setItems(Array.isArray(d) ? d : []))
      .catch(e => setError(e instanceof ApiError && e.status === 403 ? "无权限访问集成功能" : "加载失败，请刷新重试"))
      .finally(() => setLoading(false));

  useEffect(() => { load(); }, []);

  const test = async (id: string) => {
    setTesting(id);
    try {
      const d = await fetchApi<{ status?: string; error?: string }>(`/api/admin/integrations/${id}/test`, { method: "POST" });
      setItems(prev => prev.map(i => i.id === id ? { ...i, status: d.status ?? i.status, last_error: d.error ?? null } : i));
    } catch { /* ignore */ } finally { setTesting(null); }
  };

  const del = async (id: string) => {
    try { await fetchApi(`/api/admin/integrations/${id}`, { method: "DELETE" }); } catch { /* ignore */ }
    setItems(i => i.filter(x => x.id !== id));
  };

  if (error) return (
    <div className="p-8 flex flex-col items-center gap-3 text-center">
      <XCircle size={36} className="text-red-400" />
      <div className="text-red-400 font-medium">{error}</div>
      <p className="text-gray-500 text-sm">请联系平台管理员获取相应权限</p>
    </div>
  );

  const activeCount = items.filter(i => i.status === "active").length;
  const errorCount  = items.filter(i => i.status === "error").length;

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">外部系统集成</h1>
          <p className="text-gray-500 text-sm mt-1">对接 PLM / MES / ERP 等企业系统</p>
        </div>
        <button onClick={load} className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors border border-gray-700 rounded-lg px-3 py-1.5">
          <RefreshCw size={12} /> 刷新
        </button>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard icon={Plug}         label="集成总数"  value={items.length}  color="bg-blue-500/10 text-blue-400" />
        <KpiCard icon={CheckCircle2} label="正常运行"  value={activeCount}   color="bg-green-500/10 text-green-400" />
        <KpiCard icon={XCircle}      label="异常状态"  value={errorCount}    color="bg-red-500/10 text-red-400" />
        <KpiCard icon={Clock}        label="停用数量"  value={items.length - activeCount - errorCount} color="bg-gray-700/30 text-gray-400" />
      </div>

      <IntegrationForm onCreated={load} />

      {/* Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-gray-500 text-sm">
            <div className="w-4 h-4 border-2 border-gray-600 border-t-blue-400 rounded-full animate-spin" />加载中…
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="w-14 h-14 rounded-2xl bg-blue-500/8 border border-blue-500/15 flex items-center justify-center">
              <Plug size={24} className="text-blue-400/60" />
            </div>
            <p className="text-gray-400 font-medium text-sm">暂无集成配置</p>
            <p className="text-gray-600 text-xs text-center max-w-xs">展开上方表单，创建首个外部系统集成连接</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-gray-800">
              <tr>{["名称", "类型", "Endpoint", "认证", "状态", "操作"].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-medium">{h}</th>
              ))}</tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {items.map(i => (
                <tr key={i.id} className="hover:bg-gray-800/30 transition-colors">
                  <td className="px-4 py-3 text-white font-medium text-sm">{i.name}</td>
                  <td className="px-4 py-3"><span className={`text-xs font-mono font-semibold uppercase ${TYPE_COLOR[i.type] ?? "text-gray-400"}`}>{i.type}</span></td>
                  <td className="px-4 py-3 text-gray-500 text-xs truncate max-w-40">{i.endpoint ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{i.auth_type ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border ${STATUS_BADGE[i.status] ?? STATUS_BADGE.inactive}`}>{i.status}</span>
                    {i.last_error && <p className="text-red-400 text-[10px] mt-0.5 truncate max-w-32" title={i.last_error}>{i.last_error}</p>}
                  </td>
                  <td className="px-4 py-3 space-x-3">
                    <button onClick={() => test(i.id)} disabled={testing === i.id}
                      className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors">
                      {testing === i.id ? "测试中…" : "测试"}
                    </button>
                    <button onClick={() => del(i.id)} className="text-xs text-red-400 hover:text-red-300 transition-colors">删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
