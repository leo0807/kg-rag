"use client";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

type AuditEntry = { ts: number; action: string; key: string; actor: string };
type KeyInfo = { name: string };

export default function CredentialsPage() {
  const [keys, setKeys]   = useState<KeyInfo[]>([]);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing]   = useState<string | null>(null);
  const [genName, setGenName] = useState("");
  const [msg, setMsg]         = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const flash = (type: "ok" | "err", text: string) => {
    setMsg({ type, text });
    setTimeout(() => setMsg(null), 4000);
  };

  const load = async () => {
    setLoading(true);
    try {
      const [k, a] = await Promise.all([
        fetchApi<string[]>("/api/admin/security/keys"),
        fetchApi<AuditEntry[]>("/api/admin/security/keys/audit"),
      ]);
      setKeys(Array.isArray(k) ? k.map((n: string) => ({ name: n })) : []);
      setAudit(Array.isArray(a) ? a : []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const generate = async () => {
    if (!genName.trim()) return;
    setActing("gen");
    try {
      await fetchApi("/api/admin/security/keys/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: genName.trim() }),
      });
      flash("ok", `密钥 ${genName} 已生成`); setGenName(""); await load();
    } catch { flash("err", "生成失败"); }
    finally { setActing(null); }
  };

  const rotate = async (name: string) => {
    if (!confirm(`确认轮换密钥 ${name}？当前值将被替换。`)) return;
    setActing(`rotate-${name}`);
    try {
      await fetchApi(`/api/admin/security/keys/${encodeURIComponent(name)}/rotate`, { method: "POST" });
      flash("ok", `${name} 已轮换`); await load();
    } catch { flash("err", "轮换失败"); }
    finally { setActing(null); }
  };

  const fmtTime = (ts: number) => new Date(ts * 1000).toLocaleString("zh-CN");

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">凭据管理</h1>
        <p className="text-gray-400 text-sm mt-1">仅 super_admin 可见 · 密钥明文不展示</p>
      </div>

      {msg && (
        <div className={`px-4 py-2 rounded text-sm ${msg.type === "ok" ? "bg-green-900 text-green-300" : "bg-red-900 text-red-300"}`}>
          {msg.text}
        </div>
      )}

      {/* Generate new key */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 className="text-white text-sm font-medium mb-3">生成新密钥</h3>
        <div className="flex gap-3">
          <input
            className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
            placeholder="密钥名称，如 JWT_SECRET"
            value={genName}
            onChange={e => setGenName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && generate()}
          />
          <button
            onClick={generate}
            disabled={!genName.trim() || acting === "gen"}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded"
          >
            {acting === "gen" ? "生成中…" : "生成"}
          </button>
        </div>
      </div>

      {/* Key list */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <div className="px-5 py-3 bg-gray-800 text-gray-400 text-xs font-medium flex justify-between">
          <span>密钥名称</span>
          <span>操作</span>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">加载中…</div>
        ) : keys.length === 0 ? (
          <div className="p-8 text-center text-gray-500 text-sm">暂无密钥</div>
        ) : (
          <ul className="divide-y divide-gray-800">
            {keys.map(k => (
              <li key={k.name} className="flex items-center justify-between px-5 py-3">
                <div>
                  <span className="text-white text-sm font-mono">{k.name}</span>
                  <span className="ml-3 text-xs text-gray-500">••••••••••••</span>
                </div>
                <button
                  onClick={() => rotate(k.name)}
                  disabled={acting === `rotate-${k.name}`}
                  className="text-xs text-yellow-400 hover:underline disabled:opacity-50"
                >
                  {acting === `rotate-${k.name}` ? "轮换中…" : "轮换"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Audit log */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <div className="px-5 py-3 bg-gray-800 text-gray-400 text-xs font-medium">访问审计（最近 50 条）</div>
        {audit.length === 0 ? (
          <div className="p-6 text-center text-gray-500 text-sm">暂无审计记录</div>
        ) : (
          <table className="w-full text-xs">
            <thead className="text-gray-500">
              <tr>
                {["时间", "操作", "密钥", "执行者"].map(h => (
                  <th key={h} className="text-left px-4 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {audit.slice().reverse().map((e, i) => (
                <tr key={i} className="border-t border-gray-800">
                  <td className="px-4 py-2 text-gray-400">{fmtTime(e.ts)}</td>
                  <td className="px-4 py-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                      e.action === "ROTATE" ? "bg-yellow-900 text-yellow-300" :
                      e.action === "SET"    ? "bg-blue-900 text-blue-300" :
                      "bg-gray-700 text-gray-400"
                    }`}>{e.action}</span>
                  </td>
                  <td className="px-4 py-2 font-mono text-gray-300">{e.key}</td>
                  <td className="px-4 py-2 text-gray-400">{e.actor}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
