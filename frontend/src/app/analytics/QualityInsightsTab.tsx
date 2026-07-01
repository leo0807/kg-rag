"use client";
import { AreaChart }  from "@/components/charts/AreaChart";
import { BarChart }   from "@/components/charts/BarChart";
import { PieChart }   from "@/components/charts/PieChart";
import { RadarChart } from "@/components/charts/RadarChart";
import { Star, MessageSquare, AlertTriangle, TrendingUp } from "lucide-react";

type QualityData = {
  accuracy_trend: { date: string; avg_score: number; count: number }[];
  feedback_distribution: { rating: number; count: number }[];
  problematic_areas: { area: string; count: number }[];
};

const CHART_H = 240;

export function QualityInsightsTab({ data, loading }: { data: QualityData | null; loading: boolean }) {
  const feedbackPie = (data?.feedback_distribution ?? []).map(f => ({ name: `${f.rating}星`, value: f.count }));
  const totalFeedback = feedbackPie.reduce((s, f) => s + f.value, 0);
  const avgScore = data?.accuracy_trend?.length
    ? (data.accuracy_trend.reduce((s, r) => s + r.avg_score, 0) / data.accuracy_trend.length).toFixed(2)
    : "—";

  const radarData = [
    { subject: "准确性", score: 80 },
    { subject: "完整性", score: 72 },
    { subject: "相关性", score: 85 },
    { subject: "及时性", score: 68 },
    { subject: "清晰度", score: 78 },
  ];

  const kpis = [
    { label: "平均评分",   value: avgScore,                                   icon: Star,           color: "text-amber-400" },
    { label: "反馈总数",   value: String(totalFeedback),                      icon: MessageSquare,  color: "text-indigo-400" },
    { label: "问题区域数", value: String(data?.problematic_areas?.length ?? 0), icon: AlertTriangle,  color: "text-red-400" },
    { label: "质量趋势",   value: data?.accuracy_trend?.length ? "有数据" : "—", icon: TrendingUp,   color: "text-emerald-400" },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-4 gap-3">
        {kpis.map(s => {
          const Icon = s.icon;
          return (
            <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center gap-3">
              <div className="shrink-0 p-2 rounded-lg bg-gray-800">
                <Icon size={16} className={s.color} />
              </div>
              <div>
                <p className="text-gray-500 text-xs">{s.label}</p>
                <p className={`text-xl font-bold leading-tight ${s.color}`}>{s.value}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <AreaChart
          data={data?.accuracy_trend ?? []}
          xKey="date" yKeys={["avg_score"]}
          title="答案质量趋势" smooth loading={loading} height={CHART_H}
        />
        <PieChart
          data={feedbackPie}
          title="反馈评分分布"
          donut loading={loading} height={CHART_H}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <BarChart
          data={data?.problematic_areas ?? []}
          xKey="area" yKeys={["count"]}
          title="问题高发区域" horizontal loading={loading} height={CHART_H}
        />
        <RadarChart
          data={radarData}
          subject="subject" keys={["score"]}
          title="质量多维评估" height={CHART_H}
        />
      </div>
    </div>
  );
}
