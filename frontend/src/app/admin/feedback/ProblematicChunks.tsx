"use client";

import { AlertTriangle } from "lucide-react";

interface ChunkItem {
  chunk_id:   string;
  total:      number;
  errors:     number;
  error_rate: number;
}

interface Props {
  items:   ChunkItem[];
  loading: boolean;
}

export function ProblematicChunks({ items, loading }: Props) {
  if (loading) return <div className="text-xs text-gray-500 py-4">加载中…</div>;

  if (items.length === 0) {
    return (
      <div className="text-xs text-gray-600 py-6 text-center">
        暂无高错误率章节数据（需要足够的标注反馈）
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-500 border-b border-gray-700/50">
            <th className="text-left py-2 pr-4 font-medium">排名</th>
            <th className="text-left py-2 pr-4 font-medium">章节 / 文档 ID</th>
            <th className="text-right py-2 pr-4 font-medium">错误次数</th>
            <th className="text-right py-2 pr-4 font-medium">总引用</th>
            <th className="text-right py-2 font-medium">错误率</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => {
            const rateColor =
              item.error_rate >= 0.6
                ? "text-red-400"
                : item.error_rate >= 0.4
                ? "text-amber-400"
                : "text-yellow-400";
            return (
              <tr key={item.chunk_id} className="border-b border-gray-800 hover:bg-gray-800/30">
                <td className="py-2 pr-4 text-gray-500">{idx + 1}</td>
                <td className="py-2 pr-4 text-gray-300 font-mono max-w-xs truncate">
                  <div className="flex items-center gap-1.5">
                    {item.error_rate >= 0.6 && (
                      <AlertTriangle size={11} className="text-red-400 flex-shrink-0" />
                    )}
                    {item.chunk_id}
                  </div>
                </td>
                <td className="py-2 pr-4 text-right text-red-400">{item.errors}</td>
                <td className="py-2 pr-4 text-right text-gray-400">{item.total}</td>
                <td className={`py-2 text-right font-medium ${rateColor}`}>
                  {Math.round(item.error_rate * 100)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
