"use client";
import { LineChart } from "@/components/charts/LineChart";
import { BarChart }  from "@/components/charts/BarChart";
import { Gauge }     from "@/components/charts/Gauge";
import { fmtNum }    from "@/components/charts/shared";
import { Users, Search, TrendingUp, Activity } from "lucide-react";

type UsageData = {
  active_users: number;
  growth_rate: number;
  daily_query_trend: { date: string; queries: number; errors: number }[];
  top_topics: { topic: string; count: number }[];
  user_engagement: { avg_queries_per_user: number; total_queries: number };
};

const CHART_H = 240;

export function UsageInsightsTab({ data, loading }: { data: UsageData | null; loading: boolean }) {
  const growthRate = data?.growth_rate ?? 0;
  const stats = [
    { label: "活跃用户", value: fmtNum(data?.active_users ?? 0),                          icon: Users,      color: "text-indigo-400" },
    { label: "总查询量",  value: fmtNum(data?.user_engagement?.total_queries ?? 0),        icon: Search,     color: "text-emerald-400" },
    { label: "人均查询",  value: `${data?.user_engagement?.avg_queries_per_user ?? 0}次`, icon: Activity,   color: "text-amber-400" },
    { label: "增长率",    value: `${growthRate}%`,                                         icon: TrendingUp, color: growthRate >= 0 ? "text-green-400" : "text-red-400" },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        {stats.map(s => {
          const Icon = s.icon;
          return (
            <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center gap-3">
              <div className="shrink-0 p-2 rounded-lg bg-gray-800">
                <Icon size={16} className={s.color} />
              </div>
              <div>
                <p className="text-gray-500 text-xs">{s.label}</p>
                <p className={`text-xl font-bold leading-tight ${s.color}`}>{s.value}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <LineChart
          data={data?.daily_query_trend ?? []}
          xKey="date" yKeys={["queries", "errors"]}
          title="每日查询趋势" smooth loading={loading} height={CHART_H}
        />
        <BarChart
          data={data?.top_topics ?? []}
          xKey="topic" yKeys={["count"]}
          title="热门主题 Top 10" horizontal loading={loading} height={CHART_H}
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
          title="错误趋势" loading={loading} height={200}
        />
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex flex-col justify-between">
          <p className="text-white text-sm font-medium mb-3">增长摘要</p>
          <div className="space-y-3 flex-1">
            {[
              { k: "活跃用户", v: fmtNum(data?.active_users ?? 0) },
              { k: "总查询",   v: fmtNum(data?.user_engagement?.total_queries ?? 0) },
              { k: "增长率",   v: `${growthRate}%` },
            ].map(({ k, v }) => (
              <div key={k} className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">{k}</span>
                <span className="text-white text-sm font-medium">{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
