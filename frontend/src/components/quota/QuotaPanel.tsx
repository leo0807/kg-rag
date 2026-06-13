"use client";
import { useEffect, useState } from "react";
import { fetchApi, ApiError } from "@/lib/api";

type QuotaItem = { used: number | null; limit: number | null; pct: number | null };
type UsageSummary = {
  period: string;
  queries: QuotaItem;
  tokens: QuotaItem;
  storage_mb: QuotaItem;
  users: QuotaItem;
  documents: QuotaItem;
  features: Record<string, boolean>;
};

function Bar({ pct }: { pct: number | null }) {
  if (pct == null) return null;
  const color = pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-yellow-500" : "bg-blue-500";
  return (
    <div className="w-full bg-gray-700 rounded-full h-1.5">
      <div className={`${color} h-1.5 rounded-full transition-all`} style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}

function QuotaRow({ label, item }: { label: string; item: QuotaItem }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-gray-400">{label}</span>
        <span className="text-white tabular-nums">
          {(item.used ?? 0).toLocaleString()} / {item.limit == null ? "无限制" : item.limit.toLocaleString()}
          {item.limit != null && (
            <span className="text-gray-500 ml-2">({item.pct ?? 0}%)</span>
          )}
        </span>
      </div>
      <Bar pct={item.pct} />
    </div>
  );
}

export default function QuotaPanel() {
  const [data, setData] = useState<UsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<UsageSummary>("/api/admin/quota")
      .then(setData)
      .catch((e) => {
        setError(e instanceof ApiError && e.status === 403 ? "无权限查看配额" : "配额数据加载失败");
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400 text-sm">加载配额数据…</div>;
  if (error)   return <div className="text-red-400 text-sm">{error}</div>;
  if (!data)   return <div className="text-red-400 text-sm">无法获取配额信息</div>;

  const featureEntries = Object.entries(data?.features ?? {});

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-white font-medium">本月用量</h3>
        <span className="text-gray-500 text-sm">{data.period}</span>
      </div>

      <div className="bg-gray-800 rounded-lg p-5 space-y-5">
        <QuotaRow label="查询次数"   item={data.queries} />
        <QuotaRow label="LLM Tokens" item={data.tokens} />
        <QuotaRow label="存储空间 (MB)" item={data.storage_mb} />
        <QuotaRow label="用户数"     item={data.users} />
        <QuotaRow label="文档数"     item={data.documents} />
      </div>

      {featureEntries.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-5">
          <h4 className="text-gray-400 text-sm mb-3">功能开关</h4>
          <div className="grid grid-cols-2 gap-2">
            {featureEntries.map(([key, enabled]) => (
              <div key={key} className="flex items-center gap-2 text-sm">
                <div className={`w-2 h-2 rounded-full ${enabled ? "bg-green-400" : "bg-gray-600"}`} />
                <span className={enabled ? "text-white" : "text-gray-500"}>{key}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
