"use client";

import { fetchApi } from "@/lib/api";
import { Activity, AlertTriangle, Clock, TrendingUp, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ProviderStatusPanel } from "./ProviderStatusPanel";
import { StatCard } from "./StatCard";

interface StrategyRow {
  strategy: string;
  total: number;
  avg_ms: number;
  p50_ms: number;
  p95_ms: number;
  total_tokens: number;
  total_cost: number;
}

interface PerformanceData {
  days: number;
  summary: { total: number; avg_ms: number; p50_ms: number; p95_ms: number; total_tokens: number; total_cost: number };
  by_strategy: StrategyRow[];
}

interface ErrorEvent {
  id: number;
  kind: string;
  path: string;
  error_type: string;
  message: string;
  created_at: string;
}

interface ErrorData {
  days: number;
  total: number;
  events: ErrorEvent[];
  top_errors: { kind: string; error_type: string; count: number }[];
}

interface DailyRow { day: string; queries: number; cost_usd: number }
interface VolumeData { days: number; daily: DailyRow[] }

type Tab = "performance" | "errors" | "volume";

const STRATEGY_LABELS: Record<string, string> = {
  parallel: "并行RRF", sequential: "ES混合", graph_augmented: "图谱增强",
  multimodal: "多模态", multi_hop: "多跳", agent: "Agent", counterfactual: "反事实" };

export default function MetricsPage() {
  const [tab, setTab]         = useState<Tab>("performance");
  const [days, setDays]       = useState(7);
  const [perf, setPerf]       = useState<PerformanceData | null>(null);
  const [errors, setErrors]   = useState<ErrorData | null>(null);
  const [volume, setVolume]   = useState<VolumeData | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === "performance") {
        const d = await fetchApi<PerformanceData>(`/api/admin/metrics/performance?days=${days}`);
        setPerf(d);
      } else if (tab === "errors") {
        const d = await fetchApi<ErrorData>(`/api/admin/metrics/errors?days=${Math.min(days, 30)}`);
        setErrors(d);
      } else {
        const d = await fetchApi<VolumeData>(`/api/admin/metrics/volume?days=${days}`);
        setVolume(d);
      }
    } catch { /* silent */ } finally {
      setLoading(false);
    }
  }, [tab, days]);

  useEffect(() => { load(); }, [load]);

  const TABS: { id: Tab; label: string }[] = [
    { id: "performance", label: "性能指标" },
    { id: "errors",      label: "错误事件" },
    { id: "volume",      label: "查询量趋势" },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
          <Activity size={18} className="text-indigo-400" /> 系统监控
        </h1>
        <div className="flex items-center gap-3">
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="bg-gray-900 border border-gray-700 text-gray-300 text-xs rounded px-2 py-1"
          >
            {[1, 3, 7, 14, 30].map(d => (
              <option key={d} value={d}>近 {d} 天</option>
            ))}
          </select>
          <button onClick={load} disabled={loading}
            className="text-xs text-gray-500 hover:text-gray-300 disabled:opacity-40">
            {loading ? "加载中…" : "刷新"}
          </button>
        </div>
      </div>

      <ProviderStatusPanel />

      <div className="flex gap-1 mb-6 bg-gray-900 border border-gray-800 rounded-lg p-0.5 w-fit">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 rounded text-xs transition-colors ${
              tab === t.id ? "bg-indigo-600 text-white" : "text-gray-500 hover:text-gray-300"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "performance" && perf && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="总查询" value={perf.summary.total ?? 0} icon={TrendingUp} />
            <StatCard label="P50 延迟" value={`${perf.summary.p50_ms ?? 0} ms`} icon={Clock} />
            <StatCard label="P95 延迟" value={`${perf.summary.p95_ms ?? 0} ms`}
              icon={Clock} warn={(perf.summary.p95_ms ?? 0) > 5000} />
            <StatCard label="总费用" value={`$${perf.summary.total_cost ?? 0}`}
              icon={Zap} sub={`${((perf.summary.total_tokens ?? 0) / 1000).toFixed(1)}K tokens`} />
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500">
                  <th className="text-left px-4 py-2">策略</th>
                  <th className="text-right px-4 py-2">查询数</th>
                  <th className="text-right px-4 py-2">均值</th>
                  <th className="text-right px-4 py-2">P50</th>
                  <th className="text-right px-4 py-2">P95</th>
                  <th className="text-right px-4 py-2">Tokens</th>
                  <th className="text-right px-4 py-2">费用</th>
                </tr>
              </thead>
              <tbody>
                {perf.by_strategy.map(r => (
                  <tr key={r.strategy} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-4 py-2 text-gray-300">{STRATEGY_LABELS[r.strategy] ?? r.strategy}</td>
                    <td className="px-4 py-2 text-right text-gray-400">{r.total}</td>
                    <td className="px-4 py-2 text-right text-gray-400">{r.avg_ms} ms</td>
                    <td className="px-4 py-2 text-right text-gray-400">{r.p50_ms} ms</td>
                    <td className={`px-4 py-2 text-right ${r.p95_ms > 5000 ? "text-amber-400" : "text-gray-400"}`}>
                      {r.p95_ms} ms
                    </td>
                    <td className="px-4 py-2 text-right text-gray-400">{((r.total_tokens || 0) / 1000).toFixed(1)}K</td>
                    <td className="px-4 py-2 text-right text-gray-400">${r.total_cost}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "errors" && errors && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <StatCard label="错误总数" value={errors.total} icon={AlertTriangle} warn={errors.total > 0} />
            {errors.top_errors[0] && (
              <StatCard label="最常见错误" value={errors.top_errors[0].error_type}
                sub={`×${errors.top_errors[0].count}`} icon={AlertTriangle} warn />
            )}
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500">
                  <th className="text-left px-4 py-2">时间</th>
                  <th className="text-left px-4 py-2">类型</th>
                  <th className="text-left px-4 py-2">路径</th>
                  <th className="text-left px-4 py-2">错误</th>
                </tr>
              </thead>
              <tbody>
                {errors.events.map(e => (
                  <tr key={e.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                      {new Date(e.created_at).toLocaleString("zh-CN", { hour12: false })}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] ${
                        e.kind === "llm_error" ? "bg-amber-900/40 text-amber-400" : "bg-red-900/40 text-red-400"
                      }`}>{e.kind}</span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 font-mono truncate max-w-[180px]">{e.path}</td>
                    <td className="px-4 py-2 text-gray-400 truncate max-w-[280px]">
                      <span className="text-gray-500">{e.error_type}: </span>{e.message}
                    </td>
                  </tr>
                ))}
                {errors.events.length === 0 && (
                  <tr><td colSpan={4} className="px-4 py-6 text-center text-gray-600">暂无错误</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "volume" && volume && (
        <div className="space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-800 text-gray-500">
                  <th className="text-left px-4 py-2">日期</th>
                  <th className="text-right px-4 py-2">查询数</th>
                  <th className="text-right px-4 py-2">当日费用</th>
                </tr>
              </thead>
              <tbody>
                {volume.daily.map(r => (
                  <tr key={r.day} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="px-4 py-2 text-gray-400">{r.day?.slice(0, 10)}</td>
                    <td className="px-4 py-2 text-right text-gray-300">{r.queries}</td>
                    <td className="px-4 py-2 text-right text-gray-400">${r.cost_usd.toFixed(4)}</td>
                  </tr>
                ))}
                {!volume.daily.length && (
                  <tr><td colSpan={3} className="px-4 py-6 text-center text-gray-600">暂无数据</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
