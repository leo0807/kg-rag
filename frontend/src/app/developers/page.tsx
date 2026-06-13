"use client";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

type ApiKey = {
  id: string; name: string; key_prefix: string;
  scopes: string[]; rate_limit: number; is_active: boolean;
  expires_at: string | null; last_used_at: string | null; created_at: string;
  api_key?: string;
};

const SCOPES = ["query:read","documents:read","feedback:write","admin:read"];
const INPUT  = "bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500";

function CodeBlock({ code }: { lang?: string; code: string }) {
  return (
    <pre className="bg-gray-950 rounded p-4 text-xs text-green-300 overflow-auto">
      <code>{code}</code>
    </pre>
  );
}

export default function DevelopersPage() {
  const [keys, setKeys]   = useState<ApiKey[]>([]);
  const [tab, setTab]     = useState<"keys"|"docs"|"history">("keys");
  const [newKey, setNewKey] = useState<ApiKey | null>(null);
  const [form, setForm]   = useState({ name: "", scopes: ["query:read"] as string[], rate_limit: 60 });
  const [saving, setSaving] = useState(false);

  const load  = () =>
    fetchApi<ApiKey[]>("/api/admin/api-keys").then(setKeys);

  useEffect(() => { load(); }, []);

  const toggleScope = (s: string) =>
    setForm((f) => ({
      ...f,
      scopes: f.scopes.includes(s) ? f.scopes.filter((x) => x !== s) : [...f.scopes, s],
    }));

  const create = async () => {
    if (!form.name) return;
    setSaving(true);
    try {
      const k = await fetchApi<ApiKey>("/api/admin/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setNewKey(k); load();
    } finally {
      setSaving(false);
    }
  };

  const del = async (id: string) => {
    await fetchApi(`/api/admin/api-keys/${id}`, { method: "DELETE" });
    setKeys((k) => k.filter((x) => x.id !== id));
  };

  const exampleCurl = `curl -X POST https://your-domain/api/v1/query \\
  -H "X-API-Key: kg_your_api_key" \\
  -H "Content-Type: application/json" \\
  -d '{"question": "CPS 规范中的焊接温度要求是什么？"}'`;

  const examplePython = `import requests

resp = requests.post(
    "https://your-domain/api/v1/query",
    headers={"X-API-Key": "kg_your_api_key"},
    json={"question": "CPS 规范中的焊接温度要求是什么？"},
)
print(resp.json())`;

  return (
    <div className="p-6 max-w-5xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">开发者门户</h1>
        <p className="text-gray-400 text-sm mt-1">API Key 管理、接口文档与调用示例</p>
      </div>

      <div className="flex gap-2 border-b border-gray-700">
        {(["keys","docs","history"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm ${tab===t ? "border-b-2 border-blue-500 text-white" : "text-gray-400 hover:text-white"}`}>
            {t==="keys" ? "API Keys" : t==="docs" ? "接口文档" : "调用历史"}
          </button>
        ))}
      </div>

      {tab === "keys" && (
        <div className="space-y-5">
          {newKey?.api_key && (
            <div className="bg-green-900/30 border border-green-700 rounded p-4">
              <p className="text-green-300 text-sm font-medium mb-2">✓ API Key 已创建，请立即复制保存（仅显示一次）</p>
              <code className="block bg-gray-900 rounded px-3 py-2 text-green-300 text-sm break-all">{newKey.api_key}</code>
            </div>
          )}

          <div className="bg-gray-800 rounded-lg p-5 space-y-4">
            <h3 className="text-white font-medium text-sm">创建新 API Key</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs text-gray-400 mb-1">名称</label>
                <input className={`${INPUT} w-full`} value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="我的应用" />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">频率限制（/分钟）</label>
                <input type="number" className={`${INPUT} w-full`} value={form.rate_limit}
                  onChange={(e) => setForm((f) => ({ ...f, rate_limit: +e.target.value }))} />
              </div>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-2">权限范围</label>
              <div className="flex gap-2 flex-wrap">
                {SCOPES.map((s) => (
                  <button key={s} onClick={() => toggleScope(s)}
                    className={`text-xs px-2 py-1 rounded border ${form.scopes.includes(s) ? "bg-blue-700 border-blue-600 text-white" : "bg-gray-700 border-gray-600 text-gray-300"}`}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
            <button onClick={create} disabled={saving || !form.name}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-1.5 rounded">
              {saving ? "创建中…" : "生成 API Key"}
            </button>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-800 text-gray-400 text-xs">
                <tr>{["名称","Key 前缀","权限","频率限制","最后使用","操作"].map((h) => (
                  <th key={h} className="text-left px-4 py-3">{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {keys.map((k) => (
                  <tr key={k.id} className="border-t border-gray-800">
                    <td className="px-4 py-3 text-white">{k.name}</td>
                    <td className="px-4 py-3 font-mono text-gray-400 text-xs">{k.key_prefix}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-1 flex-wrap">
                        {k.scopes.map((s) => <span key={s} className="text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">{s}</span>)}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-gray-400">{k.rate_limit}/min</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{k.last_used_at?.slice(0,10) ?? "—"}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => del(k.id)} className="text-xs text-red-400 hover:underline">删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {keys.length === 0 && <div className="text-center text-gray-500 py-10 text-sm">暂无 API Key</div>}
          </div>
        </div>
      )}

      {tab === "docs" && (
        <div className="space-y-6">
          <div className="bg-gray-800 rounded-lg p-5">
            <h3 className="text-white font-medium mb-1">认证方式</h3>
            <p className="text-gray-400 text-sm mb-3">所有 v1 接口需在请求头中携带 <code className="text-green-300">X-API-Key</code></p>
            <CodeBlock lang="bash" code={exampleCurl} />
          </div>
          <div className="bg-gray-800 rounded-lg p-5">
            <h3 className="text-white font-medium mb-3">Python 示例</h3>
            <CodeBlock lang="python" code={examplePython} />
          </div>
          <div className="bg-gray-800 rounded-lg p-5">
            <h3 className="text-white font-medium mb-3">可用端点</h3>
            <div className="space-y-2 text-sm">
              {[
                ["POST /api/v1/query","问答接口","query:read"],
                ["GET  /api/v1/documents","文档列表","documents:read"],
                ["POST /api/v1/feedback","提交反馈","feedback:write"],
                ["GET  /api/v1/health","健康检查","公开"],
              ].map(([ep, desc, scope]) => (
                <div key={ep} className="flex items-center gap-3">
                  <code className="text-green-300 w-52 shrink-0">{ep}</code>
                  <span className="text-gray-300">{desc}</span>
                  <span className="text-xs text-blue-400 ml-auto">{scope}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === "history" && (
        <div className="text-gray-400 text-sm p-4">
          请点击具体 API Key 查看调用历史（GET /api/admin/api-keys/{"{id}"}/usage）
        </div>
      )}
    </div>
  );
}
