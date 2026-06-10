import type { GenerationTask } from "../types";

const SECTION_NAMES: Record<string, string> = {
  "1": "范围", "2": "引用文件", "3": "术语和定义",
  "4": "材料", "6": "技术要求", "7": "工艺规程",
  "8": "检验与试验", "9": "标识与记录",
};
const SECTION_ORDER = ["1", "2", "3", "4", "6", "7", "8", "9"];

interface Props {
  task: GenerationTask;
}

export function ProgressPanel({ task }: Props) {
  const sections = task.result_sections ?? {};
  const doneCount = Object.keys(sections).length;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      {/* Overall progress */}
      <div>
        <div className="flex justify-between text-xs text-gray-400 mb-1.5">
          <span>{task.current_step || "等待中…"}</span>
          <span>{task.progress}%</span>
        </div>
        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              task.status === "failed"
                ? "bg-red-600"
                : task.status === "done"
                  ? "bg-green-500"
                  : "bg-indigo-500"
            }`}
            style={{ width: `${task.progress}%` }}
          />
        </div>
      </div>

      {/* Chapter checklist */}
      <div className="grid grid-cols-2 gap-2">
        {SECTION_ORDER.map(num => {
          const done = !!sections[num];
          return (
            <div key={num}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs ${
                done
                  ? "border-green-800/50 bg-green-900/10 text-green-400"
                  : "border-gray-800 bg-gray-900/50 text-gray-600"
              }`}>
              <span className="font-mono w-4 shrink-0">{done ? "✓" : "○"}</span>
              <span>§{num} {SECTION_NAMES[num] ?? ""}</span>
            </div>
          );
        })}
      </div>

      {task.status === "failed" && task.error && (
        <div className="text-xs text-red-400 bg-red-900/20 border border-red-800 rounded-lg p-3">
          错误：{task.error}
        </div>
      )}

      {task.status === "done" && (
        <div className="text-xs text-green-400 text-center pt-1">
          ✓ 生成完成 — 共 {doneCount} 个章节
        </div>
      )}
    </div>
  );
}
