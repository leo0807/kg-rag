"use client";

import type { ObjectiveTask } from "../types";

export function ObjectiveEvalStageCard({ task }: { task: ObjectiveTask }) {
  const stage = getObjectiveStage(task);

  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs text-gray-500">当前阶段</div>
        <div className="text-xs rounded-full px-3 py-1 border border-gray-700 text-gray-300">
          {stage.label}
        </div>
      </div>
      <div className="mt-2 text-sm text-gray-200 leading-6">{stage.hint}</div>
      <div className="mt-2 text-xs text-gray-500">
        源文档：{task.source_doc_id || "自动检测"}
      </div>
    </div>
  );
}

function getObjectiveStage(task: ObjectiveTask) {
  if (task.status === "failed") {
    return { label: "评测失败", hint: task.error || "评测过程中发生错误。" };
  }
  if (task.status === "completed") {
    return {
      label: "评测完成",
      hint: `已完成 ${task.completed}/${task.total} 题，结果可导出 CSV。`,
    };
  }
  if (task.current_question.includes("正在解析文档")) {
    return { label: "解析文档", hint: "正在从上传文档中提取题目，请稍候。" };
  }
  if (task.current_question.includes("题目解析完成")) {
    return { label: "准备评测", hint: task.current_question };
  }
  if (task.status === "queued") {
    return { label: "已排队", hint: "任务已创建，正在等待解析文档。" };
  }
  return {
    label: `评测中 ${task.completed}/${task.total}`,
    hint: task.current_question || "正在评测客观题，请稍候。",
  };
}
