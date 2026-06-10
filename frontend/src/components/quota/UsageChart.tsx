"use client";
import { useEffect, useState } from "react";

type TenantUsage = {
  tenant_id: string;
  tenant_name: string;
  period: string;
  queries: { used: number; limit: number; pct: number };
  tokens: { used: number; limit: number; pct: number };
  storage_mb: { used: number; limit: number; pct: number };
};

function MiniBar({ pct }: { pct: number }) {
  const color = pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-yellow-400" : "bg-blue-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-700 rounded h-1.5">
        <div className={`${color} h-1.5 rounded`} style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <span className="text-xs text-gray-400 w-10 text-right">{pct}%</span>
    </div>
  );
}

export default function UsageChart() {
  const [data, setData] = useState<TenantUsage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState<"queries" | "tokens" | "storage">("queries");

  useEffect(() => {
    fetch("/api/platform/usage", {
      headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
    })
      .then((r) => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400 text-sm p-4">加载中…</div>;

  const sorted = [...data].sort((a, b) => {
    const key = sort === "storage" ? "storage_mb" : sort;
    return (b[key as keyof TenantUsage] as any).pct - (a[key as keyof TenantUsage] as any).pct;
  });

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {(["queries", "tokens", "storage"] as const).map((k) => (
          <button key={k} onClick={() => setSort(k)}
            className={`text-xs px-3 py-1 rounded ${sort === k ? "bg-blue-700 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
            {k === "queries" ? "查询次数" : k === "tokens" ? "Token 用量" : "存储空间"}
          </button>
        ))}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-800 text-gray-400 text-xs">
            <tr>
              <th className="text-left px-4 py-2">租户</th>
              <th className="px-4 py-2">查询次数</th>
              <th className="px-4 py-2">Token 用量</th>
              <th className="px-4 py-2">存储</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((t) => (
              <tr key={t.tenant_id} className="border-t border-gray-800">
                <td className="px-4 py-3 text-white font-medium">{t.tenant_name}</td>
                <td className="px-4 py-3 w-40"><MiniBar pct={t.queries.pct} /></td>
                <td className="px-4 py-3 w-40"><MiniBar pct={t.tokens.pct} /></td>
                <td className="px-4 py-3 w-40"><MiniBar pct={t.storage_mb.pct} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {sorted.length === 0 && (
          <div className="text-center text-gray-500 py-8 text-sm">暂无用量数据</div>
        )}
      </div>
    </div>
  );
}
