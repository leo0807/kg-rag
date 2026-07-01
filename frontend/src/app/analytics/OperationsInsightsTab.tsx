"use client";
import { AreaChart } from "@/components/charts/AreaChart";
import { BarChart }  from "@/components/charts/BarChart";
import { Gauge }     from "@/components/charts/Gauge";
import { Activity, Zap, AlertTriangle, TrendingUp } from "lucide-react";
import { fmtNum } from "@/components/charts/shared";

type OpsData = {
  qps_trend:      { hour: string; requests: number }[];
  error_patterns: { action: string; count: number }[];
};

const CHART_H = 240;

export function OperationsInsightsTab({ data, loading }: { data: OpsData | null; loading: boolean }) {
  const totalRequests = (data?.qps_trend ?? []).reduce((s, r) => s + r.requests, 0);
  const totalErrors   = (data?.error_patterns ?? []).reduce((s, r) => s + r.count, 0);
  const errorRate     = totalRequests > 0 ? (totalErrors / totalRequests) * 100 : 0;
  const maxQps        = Math.max(...(data?.qps_trend ?? []).map(r => r.requests), 1);
  const avgRps        = totalRequests / Math.max((data?.qps_trend ?? []).length, 1);

  const errorColor = errorRate > 5 ? "text-red-400" : errorRate > 1 ? "text-yellow-400" : "text-green-400";

  const kpis = [
    { label: "总请求数", value: fmtNum(totalRequests), icon: Activity,    color: "text-indigo-400" },
    { label: "峰值 QPS", value: fmtNum(maxQps),        icon: Zap,         color: "text-amber-400" },
    { label: "平均 RPS", value: avgRps.toFixed(1),     icon: TrendingUp,  color: "text-emerald-400" },
    { label: "错误率",   value: `${errorRate.toFixed(2)}%`, icon: AlertTriangle, color: errorColor },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        {kpis.map(s => {
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

      <AreaChart
        data={data?.qps_trend ?? []}
        xKey="hour" yKeys={["requests"]}
        title="请求量趋势（按小时）" smooth loading={loading}
        height={200}
      />

      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2">
          <BarChart
            data={data?.error_patterns ?? []}
            xKey="action" yKeys={["count"]}
            title="错误模式 Top 10" horizontal loading={loading} height={CHART_H}
          />
        </div>
        <div className="flex flex-col gap-4">
          <Gauge
            value={Math.round(errorRate * 10) / 10}
            max={20}
            title="错误率"
            unit="%"
            thresholds={[30, 60]}
          />
          <Gauge
            value={Math.min(Math.round(avgRps), 1000)}
            max={1000}
            title="平均 RPS"
            unit="req/s"
            thresholds={[50, 80]}
          />
        </div>
      </div>
    </div>
  );
}
