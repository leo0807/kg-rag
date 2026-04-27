"use client";

import { CheckCircle, ChevronDown, Loader2, Save, Trash2, XCircle } from "lucide-react";
import { useState } from "react";
import { PRESETS } from "./presets";

interface Props {
  saving: boolean;
  validating: boolean;
  validateResult: { valid: boolean; errors: string[] } | null;
  onValidate: () => void;
  onSave: (name?: string) => void;
  onPreset: (key: string) => void;
  onClear: () => void;
}

export function PipelineToolbar({ saving, validating, validateResult, onValidate, onSave, onPreset, onClear }: Props) {
  const [showPresets, setShowPresets] = useState(false);
  const [saveAsMode, setSaveAsMode] = useState(false);
  const [newName, setNewName] = useState("");

  function handleSaveAs() {
    if (!newName.trim()) return;
    onSave(newName.trim());
    setSaveAsMode(false);
    setNewName("");
  }

  return (
    <div className="flex flex-col gap-2 border-b border-gray-800 bg-gray-950 px-4 py-3">
      <div className="flex items-center gap-3">
        {/* Validate */}
        <button
          type="button"
          onClick={onValidate}
          disabled={validating}
          className="inline-flex items-center gap-1.5 rounded-xl border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs font-medium text-gray-200 hover:bg-gray-800 disabled:opacity-50"
        >
          {validating ? <Loader2 size={13} className="animate-spin" /> : null}
          验证链路
        </button>

        {/* Save */}
        <button
          type="button"
          onClick={() => onSave()}
          disabled={saving}
          className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
          保存
        </button>

        {/* Save As */}
        {!saveAsMode ? (
          <button
            type="button"
            onClick={() => setSaveAsMode(true)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-800"
          >
            另存为
          </button>
        ) : (
          <div className="flex items-center gap-1.5">
            <input
              type="text"
              placeholder="配置名称"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSaveAs(); if (e.key === "Escape") setSaveAsMode(false); }}
              autoFocus
              className="rounded-xl border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-white outline-none focus:border-indigo-500"
            />
            <button type="button" onClick={handleSaveAs} className="rounded-xl bg-indigo-600 px-2 py-1 text-xs text-white hover:bg-indigo-500">
              确认
            </button>
            <button type="button" onClick={() => setSaveAsMode(false)} className="text-xs text-gray-500 hover:text-gray-300">
              取消
            </button>
          </div>
        )}

        {/* Clear canvas */}
        <button
          type="button"
          onClick={onClear}
          className="inline-flex items-center gap-1.5 rounded-xl border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-900/20 hover:border-red-700"
          title="清空画板（不影响已保存配置）"
        >
          <Trash2 size={13} /> 清空画板
        </button>

        {/* Presets */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowPresets((v) => !v)}
            className="inline-flex items-center gap-1 rounded-xl border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs font-medium text-gray-300 hover:bg-gray-800"
          >
            预设方案 <ChevronDown size={12} />
          </button>
          {showPresets && (
            <div className="absolute left-0 top-full z-50 mt-1 min-w-[130px] rounded-2xl border border-gray-700 bg-gray-900 py-1 shadow-xl">
              {Object.entries(PRESETS).map(([key, preset]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => { onPreset(key); setShowPresets(false); }}
                  className="w-full px-4 py-2 text-left text-xs text-gray-300 hover:bg-gray-800"
                >
                  {preset.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Validation result */}
      {validateResult && (
        <div className={`flex items-start gap-2 rounded-xl px-3 py-2 text-xs ${validateResult.valid ? "bg-emerald-500/10 text-emerald-300" : "bg-red-500/10 text-red-300"}`}>
          {validateResult.valid
            ? <CheckCircle size={13} className="mt-0.5 shrink-0" />
            : <XCircle size={13} className="mt-0.5 shrink-0" />}
          <div>
            {validateResult.valid
              ? "链路验证通过，可以保存使用"
              : validateResult.errors.join("；")}
          </div>
        </div>
      )}
    </div>
  );
}
