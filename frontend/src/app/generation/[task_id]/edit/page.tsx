"use client";

import { fetchApi } from "@/lib/api";
import { ArrowLeft, Download, Flag } from "lucide-react";
import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import type { GenerationTask } from "../../types";
import { ExportDialog } from "./ExportDialog";
import { SectionEditor } from "./SectionEditor";
import { ValidationPanel } from "./ValidationPanel";

interface Props { params: Promise<{ task_id: string }> }

const SECTION_TITLES: Record<string, string> = {
  "1": "范围", "2": "引用文件", "3": "术语和定义",
  "4": "材料", "6": "技术要求", "7": "工艺规程",
  "8": "检验与试验", "9": "标识与记录",
};
const SECTION_ORDER = ["1", "2", "3", "4", "6", "7", "8", "9"];

export default function EditPage({ params }: Props) {
  const { task_id } = use(params);
  const [task, setTask]         = useState<GenerationTask | null>(null);
  const [activeNum, setActiveNum] = useState<string>("1");
  const [saving, setSaving]     = useState(false);
  const [regenNum, setRegenNum] = useState<string | null>(null);
  const [showExport, setShowExport] = useState(false);

  const load = useCallback(async () => {
    const t = await fetchApi<GenerationTask>(`/api/generation/tasks/${task_id}`);
    setTask(t);
    const sections = t.result_sections ?? {};
    if (!sections[activeNum] && Object.keys(sections).length > 0) {
      setActiveNum(Object.keys(sections)[0]);
    }
  }, [task_id, activeNum]);

  useEffect(() => { load(); }, [task_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSave = async (content: string) => {
    setSaving(true);
    try {
      await fetchApi(`/api/generation/tasks/${task_id}/section/${activeNum}`, {
        method: "PUT",
        body: JSON.stringify({ content }),
        headers: { "Content-Type": "application/json" },
      });
      setTask(t => t ? {
        ...t, result_sections: { ...t.result_sections, [activeNum]: content }
      } : t);
    } finally { setSaving(false); }
  };

  const handleRegenerate = async (num: string) => {
    setRegenNum(num);
    try {
      await fetchApi(`/api/generation/tasks/${task_id}/regenerate/${num}`, { method: "POST" });
      // Poll for completion
      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 3000));
        const t = await fetchApi<GenerationTask>(`/api/generation/tasks/${task_id}`);
        if (t.current_step?.includes("完成")) { setTask(t); break; }
        if (i % 5 === 0) setTask(t);
      }
    } finally { setRegenNum(null); }
  };

  const handleFinalize = async () => {
    if (!confirm("定稿后标记为已定稿状态，确认？")) return;
    await fetchApi(`/api/generation/tasks/${task_id}/finalize`, { method: "POST" });
    await load();
  };

  if (!task) {
    return <div className="flex-1 flex items-center justify-center bg-gray-950 text-xs text-gray-500">加载中…</div>;
  }

  const sections = task.result_sections ?? {};
  const presentSections = SECTION_ORDER.filter(n => sections[n]);
  const currentContent  = sections[activeNum] ?? "";

  return (
    <div className="flex-1 flex flex-col bg-gray-950 overflow-hidden">
      {/* Topbar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-800 shrink-0">
        <div className="flex items-center gap-3">
          <Link href={`/generation/${task_id}`} className="text-gray-600 hover:text-gray-400">
            <ArrowLeft size={15} />
          </Link>
          <span className="text-sm font-medium text-gray-200 truncate max-w-xs">{task.task_name}</span>
          {task.status === "finalized" && (
            <span className="text-[10px] px-1.5 py-0.5 bg-indigo-900/40 border border-indigo-800 rounded text-indigo-400">
              已定稿
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {task.status !== "finalized" && (
            <button onClick={handleFinalize}
              className="flex items-center gap-1 px-2.5 py-1 text-xs text-gray-400 hover:text-white border border-gray-700 hover:border-gray-600 rounded">
              <Flag size={11} /> 定稿
            </button>
          )}
          <button onClick={() => setShowExport(true)}
            className="flex items-center gap-1 px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded">
            <Download size={11} /> 导出
          </button>
        </div>
      </div>

      {/* Three-column layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: section list */}
        <div className="w-44 shrink-0 border-r border-gray-800 overflow-auto">
          {presentSections.map(num => {
            const hasIssues = task.validation_report?.issues.some(i => i.section === num);
            return (
              <button key={num} type="button"
                onClick={() => setActiveNum(num)}
                className={`w-full text-left px-3 py-2.5 text-xs border-b border-gray-800/50 flex items-center justify-between transition-colors ${
                  activeNum === num
                    ? "bg-indigo-900/20 text-indigo-300 border-l-2 border-l-indigo-600"
                    : "text-gray-400 hover:bg-gray-800/50"
                }`}>
                <span>§{num} {SECTION_TITLES[num] ?? ""}</span>
                {hasIssues && <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />}
              </button>
            );
          })}
        </div>

        {/* Center: editor */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <SectionEditor
            sectionNum={activeNum}
            sectionTitle={SECTION_TITLES[activeNum] ?? ""}
            content={currentContent}
            saving={saving}
            regenerating={regenNum === activeNum}
            onSave={handleSave}
            onRegenerate={() => handleRegenerate(activeNum)}
          />
        </div>

        {/* Right: validation */}
        {task.validation_report && (
          <div className="w-64 shrink-0 border-l border-gray-800 overflow-hidden flex flex-col">
            <ValidationPanel
              report={task.validation_report}
              activeSection={activeNum}
              onSectionClick={setActiveNum}
            />
          </div>
        )}
      </div>

      {showExport && (
        <ExportDialog
          taskId={task_id}
          taskName={task.task_name}
          onClose={() => setShowExport(false)}
        />
      )}
    </div>
  );
}
