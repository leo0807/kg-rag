"use client";

import { Clock, Database, Search, Zap } from "lucide-react";

interface ServiceInfo {
  state: "ok" | "down" | "unknown";
  error: string;
  latency_ms: number;
  last_check: number | null;
}

function serviceTone(state: ServiceInfo["state"]) {
  return state === "ok"
    ? "bg-emerald-500/10 text-emerald-400"
    : "bg-red-500/10 text-red-400";
}

const SERVICE_DEFS = [
  { key: "neo4j",         name: "Neo4j 图数据库",         Icon: Database, color: "text-indigo-400", bg: "bg-indigo-500/10" },
  { key: "milvus",        name: "Milvus 向量库",          Icon: Zap,      color: "text-amber-400",  bg: "bg-amber-500/10"  },
  { key: "elasticsearch", name: "Elasticsearch 全文引擎", Icon: Search,   color: "text-emerald-400",bg: "bg-emerald-500/10"},
] as const;

interface Props {
  services: { neo4j: ServiceInfo; milvus: ServiceInfo; elasticsearch: ServiceInfo };
}

export function ServiceGrid({ services }: Props) {
  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
      {SERVICE_DEFS.map(({ key, name, Icon, color, bg }) => {
        const data = services[key];
        return (
          <div key={key} className="rounded-2xl border border-gray-800 bg-gray-900 p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <div className={`rounded-lg p-2 ${bg}`}>
                <Icon className={color} size={20} />
              </div>
              <div className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${serviceTone(data.state)}`}>
                {data.state}
              </div>
            </div>
            <div className="text-xs font-medium text-gray-500">{name}</div>
            <div className="mt-1 flex items-baseline gap-1 text-3xl font-bold text-white">
              {Math.round(data.latency_ms)}
              <span className="text-sm font-normal text-gray-600">ms</span>
            </div>
            <div className="mt-4 flex items-center justify-between border-t border-gray-800 pt-4 text-[11px] text-gray-500">
              <div className="flex items-center gap-1.5">
                <Clock size={12} />
                {data.last_check ? new Date(data.last_check * 1000).toLocaleTimeString() : "N/A"}
              </div>
              <span className="max-w-[45%] truncate text-right text-gray-600">
                {data.error || "运行正常"}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
