"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { ChevronLeft } from "lucide-react";

type ActivitySummary = {
  user_id: string;
  total_actions: number;
  action_breakdown: Record<string, number>;
  resource_breakdown: Record<string, number>;
  recent: {
    id: string; event_type: string; action: string;
    resource_type: string | null; resource_name: string | null;
    success: boolean; timestamp: string; request_path: string | null;
  }[];
};

const ACTION_COLOR: Record<string, string> = {
  create: "text-green-400", delete: "text-red-400", update: "text-yellow-400",
  read: "text-blue-400", auth: "text-purple-400",
};

export default function UserActivityPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ActivitySummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<ActivitySummary>(`/api/admin/audit/users/${id}/activity?limit=100`)
      .then((d) => { if (d) setData(d); })
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <div className="flex-1 overflow-y-auto bg-gray-950 p-5 space-y-5">
      <div className="flex items-center gap-3">
        <Link href="/admin/audit" className="text-gray-400 hover:text-white">
          <ChevronLeft size={18} />
        </Link>
        <div>
          <h1 className="text-lg font-semibold text-white">用户活动详情</h1>
          <p className="text-xs text-gray-500 mt-0.5">{id}</p>
        </div>
      </div>

      {loading && <p className="text-sm text-gray-500">加载中…</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <StatCard label="总操作数" value={data.total_actions} />
            {Object.entries(data.action_breakdown).map(([k, v]) => (
              <StatCard key={k} label={k} value={v} color={ACTION_COLOR[k]} />
            ))}
          </div>

          {Object.keys(data.resource_breakdown).length > 0 && (
            <div className="bg-gray-900 rounded-lg p-4">
              <p className="text-xs font-medium text-gray-400 mb-3">资源分布</p>
              <div className="flex flex-wrap gap-2">
                {Object.entries(data.resource_breakdown).map(([k, v]) => (
                  <span key={k} className="px-2 py-0.5 text-xs rounded bg-gray-800 text-gray-300">
                    {k}: {v}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="bg-gray-900 rounded-lg overflow-hidden">
            <p className="text-xs font-medium text-gray-400 px-4 py-3 border-b border-gray-800">
              最近 {data.recent.length} 条操作
            </p>
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-gray-500 border-b border-gray-800">
                  <th className="px-4 py-2 font-medium">时间</th>
                  <th className="px-4 py-2 font-medium">事件</th>
                  <th className="px-4 py-2 font-medium">路径</th>
                  <th className="px-4 py-2 font-medium">结果</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/40">
                {data.recent.map((e) => (
                  <tr key={e.id} className="hover:bg-gray-800/40">
                    <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                      {new Date(e.timestamp).toLocaleString("zh-CN", {
                        month: "2-digit", day: "2-digit",
                        hour: "2-digit", minute: "2-digit", second: "2-digit",
                      })}
                    </td>
                    <td className={`px-4 py-2 font-medium ${ACTION_COLOR[e.action] ?? "text-gray-300"}`}>
                      {e.event_type}
                    </td>
                    <td className="px-4 py-2 text-gray-400 truncate max-w-xs">{e.request_path ?? "—"}</td>
                    <td className="px-4 py-2">
                      <span className={`w-2 h-2 rounded-full inline-block ${e.success ? "bg-green-500" : "bg-red-500"}`} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color ?? "text-white"}`}>{value}</p>
    </div>
  );
}
