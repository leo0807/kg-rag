"use client";
import { fetchApi } from "@/lib/api";
import { CheckCircle, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

interface ProviderStatus {
  name: string;
  model: string;
  healthy: boolean;
  consecutive_failures: number;
  total_calls: number;
  success_rate: number;
  last_failure_reason: string;
}

interface PoolStatus {
  enabled: boolean;
  providers: ProviderStatus[];
}

export function ProviderStatusPanel() {
  const [data, setData] = useState<PoolStatus | null>(null);

  useEffect(() => {
    fetchApi<PoolStatus>("/api/admin/metrics/llm-providers")
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data?.enabled) return null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6">
      <h2 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
        LLM Provider 故障转移
      </h2>
      <div className="space-y-2">
        {data.providers.map(p => (
          <div key={p.name} className="flex items-center gap-3 text-xs">
            {p.healthy
              ? <CheckCircle size={13} className="text-green-400 shrink-0" />
              : <XCircle size={13} className="text-red-400 shrink-0" />
            }
            <span className="text-gray-300 w-24 shrink-0">{p.name}</span>
            <span className="text-gray-500 font-mono truncate flex-1 max-w-[200px]">{p.model}</span>
            <span className={p.healthy ? "text-green-400 w-14 shrink-0" : "text-red-400 w-14 shrink-0"}>
              {p.healthy ? "健康" : `失败 ×${p.consecutive_failures}`}
            </span>
            <span className="text-gray-600 w-20 shrink-0 text-right">
              成功率 {(p.success_rate * 100).toFixed(0)}%
            </span>
            <span className="text-gray-600 w-16 shrink-0 text-right">
              {p.total_calls} 次
            </span>
            {!p.healthy && p.last_failure_reason && (
              <span className="text-amber-700 truncate max-w-[240px]" title={p.last_failure_reason}>
                {p.last_failure_reason}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
