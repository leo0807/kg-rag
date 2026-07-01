"use client";

import { fetchApi } from "@/lib/api";
import { Activity, AlertTriangle, RefreshCw, Server, Users, Waves } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ServiceGrid } from "./ServiceGrid";
import { PressurePresenceRow } from "./PressurePresenceRow";

interface ServiceInfo { state: "ok" | "down" | "unknown"; error: string; latency_ms: number; last_check: number | null }
interface OpsOverview {
  runtime: { total: number; running: number; failed: number; queued: number; completed: number };
  services: { neo4j: ServiceInfo; milvus: ServiceInfo; elasticsearch: ServiceInfo };
  presence: { active_users: number; requests_1m: number; active_window_seconds: number; users: { user_id: string; username: string; full_name: string; last_seen: number }[] };
  pressure: { level: "low" | "medium" | "high"; score: number; summary: string; factors: string[] };
}

function pressureTone(level: OpsOverview["pressure"]["level"]) {
  if (level === "high")   return "bg-red-500/15 text-red-300 border-red-500/20";
  if (level === "medium") return "bg-amber-500/15 text-amber-300 border-amber-500/20";
  return "bg-emerald-500/15 text-emerald-300 border-emerald-500/20";
}

export default function SystemStatusPage() {
  const [overview,   setOverview]   = useState<OpsOverview | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error,      setError]      = useState("");

  const fetchStatus = useCallback(async () => {
    try {
      setRefreshing(true);
      const data = await fetchApi<OpsOverview>("/api/admin/ops/overview");
      setOverview(data); setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载系统状态失败");
    } finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => {
    fetchStatus();
    const timer = window.setInterval(fetchStatus, 10000);
    return () => window.clearInterval(timer);
  }, [fetchStatus]);

  if (loading) {
    return <div className="flex flex-1 items-center justify-center bg-gray-950">
      <RefreshCw className="animate-spin text-indigo-500" size={32} />
    </div>;
  }

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-8">
      <div className="mx-auto max-w-6xl space-y-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
              <Server className="text-indigo-500" /> 系统状态监控器
            </h1>
            <p className="mt-1 text-sm text-gray-500">实时观察在线人数、请求压力、任务排队和核心依赖健康度。</p>
          </div>
          <button onClick={fetchStatus} disabled={refreshing}
            className="flex items-center gap-2 rounded-lg border border-gray-800 bg-gray-900 px-4 py-2 text-sm transition-colors hover:bg-gray-800 disabled:opacity-50">
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
            {refreshing ? "刷新中..." : "立即刷新"}
          </button>
        </div>

        {error && (
          <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {overview && (
          <>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4 stagger-scale">
              {[
                { label: "实时在线人数",    value: overview.presence.active_users,
                  sub: `近 ${Math.round(overview.presence.active_window_seconds / 60)} 分钟活跃`,
                  Icon: Users,         tone: "text-sky-300 bg-sky-500/10" },
                { label: "近 1 分钟请求量", value: overview.presence.requests_1m,
                  sub: "系统入口实时吞吐",
                  Icon: Waves,         tone: "text-violet-300 bg-violet-500/10" },
                { label: "运行中任务",      value: overview.runtime.running,
                  sub: `排队 ${overview.runtime.queued} / 失败 ${overview.runtime.failed}`,
                  Icon: Activity,      tone: "text-indigo-300 bg-indigo-500/10" },
                { label: "系统压力",        value: overview.pressure.level.toUpperCase(),
                  sub: `评分 ${overview.pressure.score}`,
                  Icon: AlertTriangle, tone: pressureTone(overview.pressure.level) },
              ].map(item => (
                <div key={item.label} className="rounded-2xl border border-gray-800 bg-gray-900 p-5 shadow-xl">
                  <div className="mb-4 flex items-center justify-between">
                    <div className={`rounded-xl p-2 ${item.tone}`}><item.Icon size={18} /></div>
                    <span className="text-[10px] uppercase tracking-[0.24em] text-gray-600">Live</span>
                  </div>
                  <div className="text-xs text-gray-500">{item.label}</div>
                  <div className="mt-1 text-3xl font-bold text-white">{item.value}</div>
                  <div className="mt-2 text-xs text-gray-600">{item.sub}</div>
                </div>
              ))}
            </div>

            <ServiceGrid services={overview.services} />
            <PressurePresenceRow pressure={overview.pressure} presence={overview.presence} />
          </>
        )}
      </div>
    </div>
  );
}
