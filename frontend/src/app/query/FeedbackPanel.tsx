"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { toast } from "sonner";

const ACCURACY_OPTIONS = [
  { value: "correct",  label: "正确" },
  { value: "partial",  label: "部分正确" },
  { value: "wrong",    label: "错误" },
] as const;

const COMPLETENESS_OPTIONS = [
  { value: "complete",  label: "完整" },
  { value: "partial",   label: "不完整" },
  { value: "missing",   label: "缺失关键信息" },
] as const;

const ERROR_TYPE_OPTIONS = [
  { value: "wrong_doc",        label: "引用了错误的规范文档" },
  { value: "hallucination",    label: "编造了不存在的内容" },
  { value: "value_error",      label: "数值或参数错误" },
  { value: "incomplete",       label: "答案不完整" },
  { value: "irrelevant_source",label: "来源章节不相关" },
];

interface Props {
  question:  string;
  answer:    string;
  sources?:  object[];
  strategy?: string;
  onClose:   () => void;
  onSubmitted?: (feedbackId: number) => void;
}

export function FeedbackPanel({ question, answer, sources, strategy, onClose, onSubmitted }: Props) {
  const [accuracy,       setAccuracy]       = useState<string>("");
  const [completeness,   setCompleteness]   = useState<string>("");
  const [errorTypes,     setErrorTypes]     = useState<string[]>([]);
  const [comment,        setComment]        = useState("");
  const [correctAnswer,  setCorrectAnswer]  = useState("");
  const [submitting,     setSubmitting]     = useState(false);
  const [done,           setDone]           = useState(false);

  function toggleErrorType(v: string) {
    setErrorTypes(prev => prev.includes(v) ? prev.filter(t => t !== v) : [...prev, v]);
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      const token = localStorage.getItem("token") ?? "";
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          question,
          answer,
          sources:        sources ?? [],
          rating:         0,
          strategy:       strategy ?? "parallel",
          accuracy:       accuracy || undefined,
          error_types:    errorTypes,
          correct_answer: correctAnswer || undefined,
        }),
      });
      if (res.ok) {
        const d = await res.json();
        setDone(true);
        toast.success("反馈已提交，感谢您的标注");
        onSubmitted?.(d.id);
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="mt-3 pt-3 border-t border-gray-800 text-xs text-gray-500">
        ✓ 感谢标注，您的反馈将帮助持续改进系统
      </div>
    );
  }

  return (
    <div className="mt-3 pt-3 border-t border-gray-800 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-400">详细标注</span>
        <button type="button" onClick={onClose} className="text-gray-600 hover:text-gray-400">
          <X size={14} />
        </button>
      </div>

      {/* 准确性 */}
      <div>
        <div className="text-xs text-gray-500 mb-1.5">准确性</div>
        <div className="flex gap-2">
          {ACCURACY_OPTIONS.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setAccuracy(opt.value)}
              className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
                accuracy === opt.value
                  ? "bg-[#1B6BB5] border-[#1B6BB5] text-white"
                  : "border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 完整性 */}
      <div>
        <div className="text-xs text-gray-500 mb-1.5">完整性</div>
        <div className="flex gap-2 flex-wrap">
          {COMPLETENESS_OPTIONS.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setCompleteness(opt.value)}
              className={`px-2.5 py-1 rounded-full text-xs border transition-colors ${
                completeness === opt.value
                  ? "bg-[#1B6BB5] border-[#1B6BB5] text-white"
                  : "border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 错误类型 */}
      <div>
        <div className="text-xs text-gray-500 mb-1.5">错误类型（可多选）</div>
        <div className="space-y-1.5">
          {ERROR_TYPE_OPTIONS.map(opt => (
            <label key={opt.value} className="flex items-center gap-2 cursor-pointer group">
              <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors flex-shrink-0 ${
                errorTypes.includes(opt.value)
                  ? "bg-[#1B6BB5] border-[#1B6BB5]"
                  : "border-gray-600 group-hover:border-gray-400"
              }`}>
                {errorTypes.includes(opt.value) && (
                  <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                    <path d="M1 3L3 5L7 1" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                )}
              </div>
              <span
                className="text-xs text-gray-400 group-hover:text-gray-300"
                onClick={() => toggleErrorType(opt.value)}
              >
                {opt.label}
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* 备注 */}
      <textarea
        value={comment}
        onChange={e => setComment(e.target.value)}
        placeholder="补充说明（可选）..."
        rows={2}
        className="w-full bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 placeholder-gray-600 outline-none focus:border-gray-600 resize-none"
      />

      {/* 正确答案 */}
      <textarea
        value={correctAnswer}
        onChange={e => setCorrectAnswer(e.target.value)}
        placeholder="提供正确答案（可选）..."
        rows={2}
        className="w-full bg-gray-800/60 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-300 placeholder-gray-600 outline-none focus:border-gray-600 resize-none"
      />

      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting || (!accuracy && errorTypes.length === 0)}
          className="px-4 py-1.5 bg-[#1B6BB5] text-white text-xs rounded-lg hover:bg-[#1558A0] disabled:opacity-40 transition-colors"
        >
          {submitting ? "提交中…" : "提交标注"}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-1.5 bg-gray-800 text-gray-400 text-xs rounded-lg hover:text-white transition-colors"
        >
          取消
        </button>
      </div>
    </div>
  );
}
