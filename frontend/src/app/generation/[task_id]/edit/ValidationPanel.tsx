import type { ValidationReport } from "../../types";

const SEV_COLORS: Record<string, string> = {
  critical: "border-red-800 bg-red-900/20 text-red-400",
  major:    "border-amber-800 bg-amber-900/20 text-amber-400",
  minor:    "border-gray-700 bg-gray-900/30 text-gray-400",
};
const SEV_LABELS: Record<string, string> = {
  critical: "严重", major: "主要", minor: "次要",
};

interface Props {
  report: ValidationReport;
  activeSection: string | null;
  onSectionClick: (s: string) => void;
}

export function ValidationPanel({ report, activeSection, onSectionClick }: Props) {
  const filtered = activeSection
    ? report.issues.filter(i => i.section === activeSection)
    : report.issues;

  return (
    <div className="flex flex-col h-full">
      {/* Score */}
      <div className="px-4 py-3 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-gray-400">质量评分</span>
          <span className={`text-lg font-semibold ${
            report.overall_score >= 80 ? "text-green-400" : "text-amber-400"
          }`}>
            {report.overall_score}
          </span>
        </div>
        {report.requires_human_review && (
          <p className="text-[10px] text-amber-500 mt-1">⚠ 建议人工审阅后定稿</p>
        )}
      </div>

      {/* Suggestions */}
      {report.suggestions?.length > 0 && (
        <div className="px-4 py-2 border-b border-gray-800 space-y-1">
          {report.suggestions.map((s, i) => (
            <p key={i} className="text-[10px] text-gray-500">· {s}</p>
          ))}
        </div>
      )}

      {/* Issues */}
      <div className="flex-1 overflow-auto px-3 py-2 space-y-2">
        {filtered.length === 0 && (
          <p className="text-xs text-gray-600 text-center py-4">
            {activeSection ? `§${activeSection} 无问题` : "暂无校验问题"}
          </p>
        )}
        {filtered.map((issue, i) => (
          <button key={i} type="button"
            onClick={() => onSectionClick(issue.section)}
            className={`w-full text-left p-2.5 rounded-lg border text-xs ${SEV_COLORS[issue.severity] ?? ""}`}>
            <div className="flex items-center gap-1.5 mb-1">
              <span className="font-medium">{SEV_LABELS[issue.severity]}</span>
              <span className="text-gray-600">§{issue.section}</span>
            </div>
            <p className="leading-relaxed">{issue.description}</p>
            {issue.suggestion && (
              <p className="mt-1 text-gray-600">建议：{issue.suggestion}</p>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
