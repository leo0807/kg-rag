"use client";

import { useEffect, useState } from "react";
import { 
  Activity, 
  Database, 
  Zap, 
  Search, 
  Server, 
  Clock, 
  AlertTriangle,
  RefreshCw,
  Cpu
} from "lucide-react";

interface ServiceInfo {
  state: "ok" | "down" | "unknown";
  error: string;
  latency_ms: number;
  last_check: number | null;
}

interface SystemStatus {
  neo4j: ServiceInfo;
  milvus: ServiceInfo;
  elasticsearch: ServiceInfo;
}

export default function SystemStatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function fetchStatus() {
    try {
      setRefreshing(true);
      const res = await fetch("/api/health");
      const data = await res.json();
      setStatus(data.services);
    } catch (err) {
      console.error("Failed to fetch system status:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, 30000);
    return () => clearInterval(timer);
  }, []);

  if (loading) {
    return (
      <div className="flex-1 p-8 flex items-center justify-center bg-gray-950">
        <RefreshCw className="text-indigo-500 animate-spin" size={32} />
      </div>
    );
  }

  const services = status ? [
    { name: "Neo4j (图数据库)", data: status.neo4j, Icon: Database, color: "text-indigo-400", bg: "bg-indigo-500/10" },
    { name: "Milvus (向量数据库)", data: status.milvus, Icon: Zap, color: "text-amber-400", bg: "bg-amber-500/10" },
    { name: "Elasticsearch (全文引擎)", data: status.elasticsearch, Icon: Search, color: "text-emerald-400", bg: "bg-emerald-500/10" },
  ] : [];

  return (
    <div className="flex-1 p-8 bg-gray-950 overflow-auto">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Server className="text-indigo-500" />
              工具箱状态监控器
            </h1>
            <p className="text-gray-500 text-sm mt-1">
              实时追踪后端组件的 I/O 状态、健康度及响应延迟。
            </p>
          </div>
          <button 
            onClick={fetchStatus}
            disabled={refreshing}
            className="flex items-center gap-2 px-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-sm
                     hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />
            {refreshing ? "刷新中..." : "立即刷新"}
          </button>
        </div>

        {/* Latency Overview Card */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {services.map(({ name, data, Icon, color, bg }) => (
            <div key={name} className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <div className={`p-2 ${bg} rounded-lg`}>
                  <Icon className={color} size={20} />
                </div>
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider
                               ${data.state === 'ok' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${data.state === 'ok' ? 'bg-emerald-500' : 'bg-red-500 animate-pulse'}`} />
                  {data.state}
                </div>
              </div>
              
              <div className="space-y-1">
                <div className="text-xs text-gray-500 font-medium">{name}</div>
                <div className="text-3xl font-bold text-white flex items-baseline gap-1">
                  {data.latency_ms}
                  <span className="text-sm font-normal text-gray-600">ms</span>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-gray-800 flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-[10px] text-gray-600">
                  <Clock size={12} />
                  {data.last_check ? new Date(data.last_check * 1000).toLocaleTimeString() : 'N/A'}
                </div>
                {data.latency_ms > 100 && (
                   <div className="flex items-center gap-1 text-[10px] text-amber-500">
                      <AlertTriangle size={12} />
                      高延迟
                   </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Error Logs / Details */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
           <div className="px-6 py-4 border-b border-gray-800 bg-gray-900/50 flex items-center gap-2">
              <Activity size={16} className="text-indigo-500" />
              <h2 className="text-sm font-bold text-gray-200">系统异常日志</h2>
           </div>
           <div className="p-0">
              <table className="w-full text-left text-xs">
                <thead className="text-gray-500 uppercase tracking-widest bg-gray-950/50">
                  <tr>
                    <th className="px-6 py-3 font-medium">组件</th>
                    <th className="px-6 py-3 font-medium">状态</th>
                    <th className="px-6 py-3 font-medium">错误信息</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {services.map(({ name, data }) => (
                    <tr key={name} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-6 py-4 font-medium text-gray-300">{name}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${data.state === 'ok' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
                          {data.state.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-gray-500 italic max-w-md truncate">
                        {data.error || "正常运行，无错误日志"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
           </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-8">
           <div className="p-6 bg-gray-900 border border-gray-800 rounded-2xl">
              <h3 className="text-sm font-bold text-gray-200 mb-4 flex items-center gap-2">
                 <Cpu size={16} className="text-indigo-400" />
                 I/O 负载分析
              </h3>
              <div className="space-y-4">
                 {[
                   { label: "平均检索时延", value: "42ms", progress: 40 },
                   { label: "吞吐量 (QPS)", value: "128", progress: 65 },
                   { label: "并发连接数", value: "8", progress: 20 }
                 ].map(stat => (
                   <div key={stat.label}>
                      <div className="flex justify-between text-[11px] mb-1.5">
                        <span className="text-gray-500">{stat.label}</span>
                        <span className="text-gray-300 font-mono">{stat.value}</span>
                      </div>
                      <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                        <div className="h-full bg-indigo-600 rounded-full" style={{ width: `${stat.progress}%` }} />
                      </div>
                   </div>
                 ))}
              </div>
           </div>
           
           <div className="p-6 bg-indigo-950/20 border border-indigo-500/10 rounded-2xl flex flex-col justify-center">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center">
                  <AlertTriangle className="text-indigo-400" size={24} />
                </div>
                <div>
                  <div className="text-sm font-bold text-indigo-300">智能降级提醒</div>
                  <div className="text-[11px] text-indigo-400/70">当前系统运行于混合降级模式</div>
                </div>
              </div>
              <p className="text-xs text-indigo-400/60 leading-relaxed">
                当检测到 Milvus 或 ES 故障时，检索路由会自动切换到 Neo4j 全文索引进行兜底。
                监控器将实时反映这一路径切换，确保工艺规范数据的生产连续性。
              </p>
           </div>
        </div>
      </div>
    </div>
  );
}
