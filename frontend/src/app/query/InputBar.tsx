"use client";

import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { Download, GitBranch, GitCompare } from "lucide-react";

function PipelineBadge() {
  const [hasDefault, setHasDefault] = useState(false);
  useEffect(() => {
    fetchApi<{ id: string } | null>("/api/pipeline/default", { noLogout: true })
      .then((d) => setHasDefault(!!d))
      .catch(() => {});
  }, []);
  if (!hasDefault) return null;
  return (
    <a
      href="/pipeline"
      className="inline-flex items-center gap-1.5 rounded-lg border border-indigo-700/40 bg-indigo-900/20 px-2.5 py-1 text-[11px] text-indigo-300 hover:bg-indigo-900/40"
    >
      <GitBranch size={11} /> 自定义链路
    </a>
  );
}

interface Props {
  title: string;
  compareMode: boolean;
  canExport: boolean;
  onToggleCompare: () => void;
  onExport: () => void;
}

export function InputBar({ title, compareMode, canExport, onToggleCompare, onExport }: Props) {
  return (
    <div className="flex items-center justify-between px-6 py-3 border-b border-gray-800 shrink-0">
      <div className="text-sm text-gray-400 truncate">{title}</div>
      <div className="flex items-center gap-2">
        <PipelineBadge />
        <button
          onClick={onToggleCompare}
          title="四策略对比模式"
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs border rounded-lg transition-colors ${
            compareMode
              ? "text-indigo-300 border-indigo-600 bg-indigo-900/30 hover:bg-indigo-900/50"
              : "text-gray-500 border-gray-800 hover:text-gray-300 hover:border-gray-600"
          }`}
        >
          <GitCompare size={12} />
          {compareMode ? "对比模式 ON" : "对比模式"}
        </button>
        <button
          onClick={onExport}
          disabled={!canExport}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-300 border border-gray-800 hover:border-gray-600 rounded-lg transition-colors disabled:opacity-30"
        >
          <Download size={12} /> 导出对话
        </button>
      </div>
    </div>
  );
}
