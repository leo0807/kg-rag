"use client";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

type Dashboard = {
  tenants: { total: number; active: number; suspended: number; trial: number };
  total_users: number;
  queries_this_month: number;
  expiring_soon: { id: string; name: string; ends_at: string }[];
  generated_at: string;
};

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-gray-800 rounded-lg p-5">
      <div className="text-gray-400 text-sm mb-1">{label}</div>
      <div className="text-white text-3xl font-semibold">{value.toLocaleString()}</div>
      {sub && <div className="text-gray-500 text-xs mt-1">{sub}</div>}
    </div>
  );
}

export default function PlatformDashboard() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<Dashboard>("/api/platform/dashboard")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-gray-400 p-8">加载中…</div>;
  if (!data) return <div className="text-red-400 p-8">无法加载仪表盘数据</div>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-white">平台仪表盘</h1>
        <p className="text-gray-500 text-sm mt-1">更新于 {data.generated_at.slice(0, 19).replace("T", " ")}</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <StatCard label="总租户数" value={data.tenants.total} sub={`活跃 ${data.tenants.active} · 暂停 ${data.tenants.suspended} · 试用 ${data.tenants.trial}`} />
        <StatCard label="活跃租户" value={data.tenants.active} />
        <StatCard label="平台总用户" value={data.total_users} />
        <StatCard label="本月查询量" value={data.queries_this_month} />
      </div>

      {data.expiring_soon.length > 0 && (
        <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-5">
          <h2 className="text-yellow-300 font-medium mb-3 text-sm">⚠ 即将到期租户（14天内）</h2>
          <div className="space-y-2">
            {data.expiring_soon.map((t) => (
              <div key={t.id} className="flex justify-between text-sm">
                <span className="text-white">{t.name}</span>
                <span className="text-yellow-400">{t.ends_at.slice(0, 10)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-800 rounded-lg p-5">
          <h3 className="text-white text-sm font-medium mb-4">租户状态分布</h3>
          <div className="space-y-3">
            {([
              ["active",    "活跃",   "bg-green-500"],
              ["suspended", "暂停",   "bg-red-500"],
              ["trial",     "试用",   "bg-blue-500"],
            ] as const).map(([key, label, color]) => {
              const count = data.tenants[key as keyof typeof data.tenants] as number;
              const pct = data.tenants.total ? Math.round(count / data.tenants.total * 100) : 0;
              return (
                <div key={key} className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${color}`} />
                  <span className="text-gray-300 text-sm flex-1">{label}</span>
                  <span className="text-white text-sm tabular-nums">{count}</span>
                  <div className="w-24 bg-gray-700 rounded h-1.5">
                    <div className={`${color} h-1.5 rounded`} style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-5">
          <h3 className="text-white text-sm font-medium mb-4">快速操作</h3>
          <div className="space-y-2">
            {[
              { href: "/platform/tenants/new", label: "+ 新建租户" },
              { href: "/platform/tenants",     label: "管理租户列表" },
              { href: "/platform/usage",        label: "查看全平台用量" },
            ].map((item) => (
              <a key={item.href} href={item.href}
                className="block bg-gray-700 hover:bg-gray-600 text-white text-sm px-4 py-2.5 rounded">
                {item.label}
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
