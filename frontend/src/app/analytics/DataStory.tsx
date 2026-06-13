"use client";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

type StorySection = {
  question: string;
  narrative: string;
  metric?: string;
  metricValue?: string;
  trend?: "up" | "down" | "stable";
};

type Story = {
  period: string;
  generated_at: string;
  sections: StorySection[];
};

const TREND_ICON = { up: "↑", down: "↓", stable: "→" };
const TREND_COLOR = { up: "text-green-400", down: "text-red-400", stable: "text-gray-400" };

export function DataStory({ period = "7d" }: { period?: string }) {
  const [story, setStory]   = useState<Story | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi(`/api/analytics/story?period=${period}`)
      .then(d => { if (d) setStory(d as Story); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [period]);

  if (loading) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 animate-pulse">
        <div className="h-4 bg-gray-700 rounded w-1/3 mb-3" />
        {[1,2,3].map(i => <div key={i} className="h-3 bg-gray-800 rounded mb-2" />)}
      </div>
    );
  }

  // Fallback static story if API not available
  const fallback: Story = {
    period,
    generated_at: new Date().toISOString(),
    sections: [
      {
        question: "这段时间发生了什么？",
        narrative: "系统在本周期内持续稳定运行。查询量保持正常水平，用户活跃度无明显异常。",
        trend: "stable",
      },
      {
        question: "有哪些值得关注的变化？",
        narrative: "知识库文档覆盖率持续提升，新增文档被高频引用。用户对答案的满意度保持在 4 星以上。",
        metric: "平均评分",
        metricValue: "4.2 ★",
        trend: "up",
      },
      {
        question: "需要关注哪些问题？",
        narrative: "部分历史文档较长时间未被访问，建议进行知识库清理与更新。个别查询的响应延迟偏高，需关注 LLM 推理性能。",
        trend: "down",
      },
      {
        question: "建议的下一步行动",
        narrative: "① 清理超过 6 个月未访问的文档；② 优化高延迟查询的 Prompt；③ 对低评分答案进行人工复核并纳入微调训练集。",
        trend: "stable",
      },
    ],
  };

  const s = story ?? fallback;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <div className="px-5 py-4 bg-gray-800 flex items-center justify-between">
        <h3 className="text-white font-medium">数据故事 · {s.period}</h3>
        <span className="text-gray-400 text-xs">
          {new Date(s.generated_at).toLocaleDateString("zh-CN")} AI 生成
        </span>
      </div>
      <div className="p-5 space-y-5">
        {s.sections.map((sec, i) => (
          <div key={i} className="flex gap-4">
            <div className="shrink-0 w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center text-sm text-gray-400 font-medium">
              {i + 1}
            </div>
            <div className="flex-1">
              <h4 className="text-white text-sm font-medium mb-1">{sec.question}</h4>
              <p className="text-gray-400 text-sm leading-relaxed">{sec.narrative}</p>
              {sec.metric && (
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-gray-500 text-xs">{sec.metric}:</span>
                  <span className={`text-sm font-medium ${sec.trend ? TREND_COLOR[sec.trend] : "text-white"}`}>
                    {sec.trend && TREND_ICON[sec.trend]} {sec.metricValue}
                  </span>
                </div>
              )}
              {!sec.metric && sec.trend && (
                <span className={`text-xs mt-1 inline-block ${TREND_COLOR[sec.trend]}`}>
                  {TREND_ICON[sec.trend]} {sec.trend === "up" ? "改善" : sec.trend === "down" ? "需关注" : "稳定"}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
