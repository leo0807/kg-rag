"use client";
import { LineChart } from "@/components/charts/LineChart";
import { BarChart }  from "@/components/charts/BarChart";
import { Gauge }     from "@/components/charts/Gauge";
import { fmtNum }    from "@/components/charts/shared";

type UsageData = {
  active_users: number;
  growth_rate: number;
  daily_query_trend: { date: string; queries: number; errors: number }[];
  top_topics: { topic: string; count: number }[];
  user_engagement: { avg_queries_per_user: number; total_queries: number };
};

export function UsageInsightsTab({ data, loading }: { data: UsageData | null; loading: boolean }) {
  const stats = [
    { label: "活跃用户", value: fmtNum(data?.active_users ?? 0) },
    { label: "总查询量",  value: fmtNum(data?.user_engagement?.total_queries ?? 0) },
    { label: "人均查询",  value: `${data?.user_engagement?.avg_queries_per_user ?? 0}次` },
    { label: "增长率",    value: `${data?.growth_rate ?? 0}%`,
      color: (data?.growth_rate ?? 0) >= 0 ? "text-green-400" : "text-red-400" },
  ];

  return (
    <div className="space-y-4">
      {/* KPI row */}
      <div className="grid grid-cols-4 gap-3">
        {stats.map(s => (
          <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-gray-400 text-xs">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color ?? "text-white"}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-2 gap-4">
        <LineChart
          data={data?.daily_query_trend ?? []}
          xKey="date" yKeys={["queries", "errors"]}
          title="每日查询趋势" smooth loading={loading}
        />
        <BarChart
          data={data?.top_topics ?? []}
          xKey="topic" yKeys={["count"]}
          title="热门主题 Top 10" horizontal loading={loading}
          height={280}
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Gauge
          value={data?.active_users ?? 0}
          max={Math.max((data?.active_users ?? 0) * 1.5, 100)}
          title="活跃用户仪表"
          unit="人"
        />
        <LineChart
          data={data?.daily_query_trend ?? []}
          xKey="date" yKeys={["errors"]}
          title="错误趋势" loading={loading} height={160}
        />
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <p className="text-white text-sm font-medium mb-3">增长摘要</p>
          <div className="space-y-2">
            {[
              ["活跃用户", data?.active_users ?? 0],
              ["总查询",   data?.user_engagement?.total_queries ?? 0],
              ["增长率",   `${data?.growth_rate ?? 0}%`],
            ].map(([k, v]) => (
              <div key={String(k)} className="flex justify-between text-sm">
                <span className="text-gray-400">{k}</span>
                <span className="text-white font-medium">{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
