"use client";

type ErrorEvent = { event: string; ts: number; data: { type?: string; message?: string; path?: string } };

export function LiveErrorMonitor({ events }: { events: ErrorEvent[] }) {
  const errors = events.filter(e => e.event === "error.occurred");
  const recentErrors = errors.slice(-20).reverse();

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-gray-800 flex items-center justify-between">
        <h3 className="text-white text-sm font-medium">实时错误监控</h3>
        <span className={`text-xs px-2 py-0.5 rounded ${errors.length > 0 ? "bg-red-900 text-red-300" : "bg-green-900 text-green-300"}`}>
          {errors.length} 个错误
        </span>
      </div>

      <div className="overflow-y-auto" style={{ maxHeight: 240 }}>
        {recentErrors.length === 0 ? (
          <div className="flex items-center justify-center py-10 text-gray-600 text-sm">
            ✓ 无错误事件
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-gray-800 text-gray-400">
              <tr>
                <th className="text-left px-4 py-2">时间</th>
                <th className="text-left px-4 py-2">类型</th>
                <th className="text-left px-4 py-2">消息</th>
                <th className="text-left px-4 py-2">路径</th>
              </tr>
            </thead>
            <tbody>
              {recentErrors.map((e, i) => (
                <tr key={i} className="border-t border-gray-800">
                  <td className="px-4 py-2 text-gray-500 font-mono whitespace-nowrap">
                    {new Date(e.ts * 1000).toLocaleTimeString("zh-CN")}
                  </td>
                  <td className="px-4 py-2 text-red-400">{e.data.type ?? "unknown"}</td>
                  <td className="px-4 py-2 text-gray-300 max-w-xs truncate">{e.data.message ?? ""}</td>
                  <td className="px-4 py-2 text-gray-500 font-mono">{e.data.path ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
