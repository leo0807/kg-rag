"use client";
import { AreaChart } from "@/components/charts/AreaChart";
import { BarChart }  from "@/components/charts/BarChart";
import { Gauge }     from "@/components/charts/Gauge";

type OpsData = {
  qps_trend:      { hour: string; requests: number }[];
  error_patterns: { action: string; count: number }[];
};

export function OperationsInsightsTab({ data, loading }: { data: OpsData | null; loading: boolean }) {
  const totalRequests = (data?.qps_trend ?? []).reduce((s, r) => s + r.requests, 0);
  const totalErrors   = (data?.error_patterns ?? []).reduce((s, r) => s + r.count, 0);
  const errorRate     = totalRequests > 0 ? ((totalErrors / totalRequests) * 100) : 0;

  const maxQps = Math.max(...(data?.qps_trend ?? []).map(r => r.requests), 1);
  const avgQps = totalRequests / Math.max((data?.qps_trend ?? []).length, 1);

  return (
    <div className="space-y-4">
      {/* KPI */}
      <div className="grid grid-cols-4 gap-3 stagger-scale">
        {[
          { label: "总请求数",   value: totalRequests.toLocaleString() },
          { label: "峰值 QPS",   value: maxQps.toLocaleString() },
          { label: "平均 RPS",   value: avgQps.toFixed(1) },
          { label: "错误率",     value: `${errorRate.toFixed(2)}%`,
            color: errorRate > 5 ? "text-red-400" : errorRate > 1 ? "text-yellow-400" : "text-green-400" },
        ].map(s => (
          <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-gray-400 text-xs">{s.label}</p>
            <p className={`text-2xl font-bold mt-1 ${s.color ?? "text-white"}`}>{s.value}</p>
          </div>
        ))}
      </div>

      <AreaChart
        data={data?.qps_trend ?? []}
        xKey="hour" yKeys={["requests"]}
        title="请求量趋势（按小时）" smooth loading={loading}
        height={200}
      />

      <div className="grid grid-cols-2 gap-4">
        <BarChart
          data={data?.error_patterns ?? []}
          xKey="action" yKeys={["count"]}
          title="错误模式 Top 10" horizontal loading={loading}
        />
        <div className="grid grid-cols-2 gap-3">
          <Gauge
            value={Math.round(errorRate * 10) / 10}
            max={20}
            title="错误率"
            unit="%"
            thresholds={[30, 60]}
          />
          <Gauge
            value={Math.min(Math.round(avgQps), 1000)}
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
