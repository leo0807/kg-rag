"use client";

import { ThumbsUp, ThumbsDown, MessageSquare, AlertTriangle } from "lucide-react";

interface StatsData {
  total:      number;
  positive:   number;
  negative:   number;
  avg_rating: number | null;
  accuracy_dist:  Record<string, number>;
  error_type_dist: Record<string, number>;
}

interface Props {
  data: StatsData | null;
  loading: boolean;
}

function StatCard({ icon, label, value, color }: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  icon: any; label: string; value: string | number; color: string;
}) {
  return (
    <div className="bg-gray-800/40 border border-gray-700/50 rounded-xl p-4">
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-3 ${color}`}>
        {icon}
      </div>
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}

export function FeedbackStats({ data, loading }: Props) {
  if (loading) return <div className="text-xs text-gray-500 py-4">加载中…</div>;
  if (!data) return null;

  const correctRate  = data.total > 0
    ? Math.round(((data.accuracy_dist["correct"] ?? 0) / data.total) * 100)
    : 0;

  const topErrors = Object.entries(data.error_type_dist ?? {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  const ERROR_LABELS: Record<string, string> = {
    wrong_doc:         "引用错误文档",
    hallucination:     "内容编造",
    value_error:       "数值参数错误",
    incomplete:        "答案不完整",
    irrelevant_source: "来源不相关",
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={<MessageSquare size={16} className="text-blue-400" />}
          label="总反馈数"
          value={data.total}
          color="bg-blue-500/20"
        />
        <StatCard
          icon={<ThumbsUp size={16} className="text-emerald-400" />}
          label="👍 有帮助"
          value={data.positive}
          color="bg-emerald-500/20"
        />
        <StatCard
          icon={<ThumbsDown size={16} className="text-red-400" />}
          label="👎 有问题"
          value={data.negative}
          color="bg-red-500/20"
        />
        <StatCard
          icon={<AlertTriangle size={16} className="text-amber-400" />}
          label="标注正确率"
          value={`${correctRate}%`}
          color="bg-amber-500/20"
        />
      </div>

      {topErrors.length > 0 && (
        <div className="bg-gray-800/40 border border-gray-700/50 rounded-xl p-4">
          <div className="text-sm font-medium text-gray-300 mb-3">错误类型分布</div>
          <div className="space-y-2">
            {topErrors.map(([type, count]) => {
              const total = Object.values(data.error_type_dist).reduce((a, b) => a + b, 0);
              const pct   = total > 0 ? Math.round((count / total) * 100) : 0;
              return (
                <div key={type} className="flex items-center gap-3">
                  <div className="w-28 text-xs text-gray-400 truncate">
                    {ERROR_LABELS[type] ?? type}
                  </div>
                  <div className="flex-1 bg-gray-700 rounded-full h-1.5">
                    <div
                      className="bg-[#1B6BB5] h-1.5 rounded-full transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="text-xs text-gray-400 w-10 text-right">{pct}%</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
