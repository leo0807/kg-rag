"use client";
import { useMemo } from "react";
import { LineChart } from "@/components/charts/LineChart";

type AnyEvent = { event: string; ts: number; data: Record<string, unknown> };

export function LivePerformanceMetrics({ events }: { events: AnyEvent[] }) {
  const queryEvents = events.filter(e => e.event === "query.completed");

  const latencies = useMemo(() => {
    return queryEvents.slice(-30).map((e, i) => ({
      t: i + 1,
      latency: Number(e.data.latency_ms ?? 0),
    }));
  }, [queryEvents.length]);

  const avgLatency = queryEvents.length
    ? Math.round(queryEvents.slice(-10).reduce((s, e) => s + Number(e.data.latency_ms ?? 0), 0) / Math.min(queryEvents.length, 10))
    : 0;

  const errorEvents = events.filter(e => e.event === "error.occurred");
  const errorRate = events.length > 0 ? ((errorEvents.length / events.length) * 100).toFixed(1) : "0.0";

  const stats = [
    { label: "总事件数",  value: events.length },
    { label: "查询数",    value: queryEvents.length },
    { label: "错误数",    value: errorEvents.length, red: errorEvents.length > 0 },
    { label: "平均延迟",  value: `${avgLatency}ms`, red: avgLatency > 3000 },
    { label: "错误率",    value: `${errorRate}%`, red: Number(errorRate) > 5 },
  ];

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-800">
        <h3 className="text-white text-sm font-medium">实时性能指标</h3>
      </div>
      <div className="p-4 space-y-4">
        <div className="grid grid-cols-5 gap-2">
          {stats.map(s => (
            <div key={s.label} className="text-center">
              <p className="text-gray-500 text-xs">{s.label}</p>
              <p className={`text-lg font-bold mt-0.5 ${s.red ? "text-red-400" : "text-white"}`}>
                {String(s.value)}
              </p>
            </div>
          ))}
        </div>
        <LineChart
          data={latencies}
          xKey="t"
          yKeys={["latency"]}
          title="近 30 次查询延迟 (ms)"
          height={160}
          smooth
          unit="ms"
        />
      </div>
    </div>
  );
}
