"use client";

import { useState } from "react";
import { CheckCircle, ChevronDown, ChevronUp } from "lucide-react";

interface ErrorCase {
  id:             number;
  question:       string;
  answer:         string;
  rating:         number;
  accuracy:       string | null;
  error_types:    string[];
  correct_answer: string | null;
  comment:        string | null;
  strategy:       string;
  status:         string;
  created_at:     string;
}

interface Props {
  items:   ErrorCase[];
  loading: boolean;
  onResolve: (id: number) => void;
}

const ACCURACY_LABEL: Record<string, string> = {
  correct: "正确",
  partial: "部分正确",
  wrong:   "错误",
};

const ERROR_LABEL: Record<string, string> = {
  wrong_doc:         "错误文档",
  hallucination:     "内容编造",
  value_error:       "数值错误",
  incomplete:        "不完整",
  irrelevant_source: "来源不相关",
};

function CaseRow({ item, onResolve }: { item: ErrorCase; onResolve: () => void }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-gray-700/50 rounded-lg overflow-hidden">
      <div
        className="flex items-start gap-3 p-3 cursor-pointer hover:bg-gray-800/30 transition-colors"
        onClick={() => setExpanded(v => !v)}
      >
        <div className="flex-1 min-w-0">
          <div className="text-xs text-gray-300 truncate">{item.question}</div>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            {item.accuracy && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                item.accuracy === "wrong" ? "bg-red-500/20 text-red-400"
                : item.accuracy === "partial" ? "bg-amber-500/20 text-amber-400"
                : "bg-emerald-500/20 text-emerald-400"
              }`}>
                {ACCURACY_LABEL[item.accuracy] ?? item.accuracy}
              </span>
            )}
            {item.error_types.map(t => (
              <span key={t} className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-700 text-gray-400">
                {ERROR_LABEL[t] ?? t}
              </span>
            ))}
            {item.status === "resolved" && (
              <span className="text-[10px] text-emerald-500">✓ 已处理</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-[10px] text-gray-600">
            {item.created_at ? new Date(item.created_at).toLocaleDateString("zh-CN") : ""}
          </span>
          {expanded ? <ChevronUp size={12} className="text-gray-500" /> : <ChevronDown size={12} className="text-gray-500" />}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-700/50 p-3 space-y-2 bg-gray-900/30">
          <div>
            <div className="text-[10px] text-gray-600 mb-1">AI 回答（节选）</div>
            <div className="text-xs text-gray-400 line-clamp-3">{item.answer}</div>
          </div>
          {item.correct_answer && (
            <div>
              <div className="text-[10px] text-gray-600 mb-1">用户提供的正确答案</div>
              <div className="text-xs text-emerald-400">{item.correct_answer}</div>
            </div>
          )}
          {item.comment && (
            <div>
              <div className="text-[10px] text-gray-600 mb-1">用户备注</div>
              <div className="text-xs text-gray-400">{item.comment}</div>
            </div>
          )}
          {item.status !== "resolved" && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onResolve(); }}
              className="flex items-center gap-1.5 px-3 py-1 bg-emerald-600/20 text-emerald-400 text-xs rounded-lg hover:bg-emerald-600/30 transition-colors"
            >
              <CheckCircle size={12} />
              标记为已处理
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function ErrorCaseList({ items, loading, onResolve }: Props) {
  const [filter, setFilter] = useState<string>("all");

  if (loading) return <div className="text-xs text-gray-500 py-4">加载中…</div>;

  const filtered = filter === "all" ? items
    : items.filter(i => i.accuracy === filter || i.error_types.includes(filter));

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        {["all", "wrong", "partial", "hallucination", "value_error"].map(f => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
              filter === f
                ? "bg-[#1B6BB5] text-white"
                : "border border-gray-700 text-gray-500 hover:border-gray-500"
            }`}
          >
            {f === "all" ? "全部" : f === "wrong" ? "标注错误" : f === "partial" ? "部分正确" : ERROR_LABEL[f] ?? f}
          </button>
        ))}
      </div>
      {filtered.length === 0 ? (
        <div className="text-xs text-gray-600 py-4 text-center">暂无错误案例</div>
      ) : (
        <div className="space-y-2">
          {filtered.map(item => (
            <CaseRow key={item.id} item={item} onResolve={() => onResolve(item.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
