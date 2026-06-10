"use client";

import { RefreshCw, Save } from "lucide-react";
import { useEffect, useState } from "react";

interface Props {
  sectionNum:  string;
  sectionTitle:string;
  content:     string;
  saving:      boolean;
  regenerating:boolean;
  onSave:      (content: string) => void;
  onRegenerate:() => void;
}

export function SectionEditor({
  sectionNum, sectionTitle, content, saving, regenerating, onSave, onRegenerate,
}: Props) {
  const [draft, setDraft] = useState(content);
  const dirty = draft !== content;

  useEffect(() => { setDraft(content); }, [content]);

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-800">
        <span className="text-sm font-medium text-gray-200">
          §{sectionNum} {sectionTitle}
        </span>
        <div className="flex items-center gap-2">
          <button type="button" onClick={onRegenerate} disabled={regenerating || saving}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 disabled:opacity-40">
            <RefreshCw size={11} className={regenerating ? "animate-spin" : ""} />
            重新生成
          </button>
          <button type="button"
            onClick={() => onSave(draft)}
            disabled={!dirty || saving}
            className="flex items-center gap-1 px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs rounded">
            <Save size={11} />
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>

      {/* Editor */}
      <textarea
        value={draft}
        onChange={e => setDraft(e.target.value)}
        disabled={regenerating}
        className="flex-1 w-full bg-gray-950 text-gray-200 text-sm leading-relaxed px-5 py-4 resize-none focus:outline-none font-mono disabled:opacity-60"
        placeholder={regenerating ? "重新生成中…" : "在此编辑章节内容…"}
      />

      {/* Word count */}
      <div className="px-4 py-1.5 border-t border-gray-800 text-[10px] text-gray-600 flex justify-between">
        <span>{draft.split(/\s+/).filter(Boolean).length} 词</span>
        {dirty && <span className="text-amber-600">未保存</span>}
      </div>
    </div>
  );
}
