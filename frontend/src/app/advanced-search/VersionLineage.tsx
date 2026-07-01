"use client";

import { ArrowUpRight, ArrowDownRight, Minus } from "lucide-react";

interface VersionDoc { id: string; title: string; version: string }
export interface VersionData {
  doc_id: string; title: string; version: string;
  newer_versions: VersionDoc[]; older_versions: VersionDoc[];
}

export function VersionLineage({ data }: { data: VersionData }) {
  return (
    <div className="space-y-3">
      {data.newer_versions.map(d => (
        <div key={d.id} className="flex items-center gap-3 px-4 py-3 bg-gray-900/60 border border-gray-800 rounded-xl">
          <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
            <ArrowUpRight size={13} className="text-emerald-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs text-emerald-500 font-medium mb-0.5">更新版本（此版本已被替代）</div>
            <div className="text-sm text-gray-300 truncate">{d.title || d.id}</div>
          </div>
          {d.version && <span className="text-xs text-gray-600 font-mono shrink-0">v{d.version}</span>}
        </div>
      ))}

      <div className="flex items-center gap-3 px-4 py-3 bg-indigo-950/40 border border-indigo-700/40 rounded-xl">
        <div className="w-7 h-7 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center shrink-0">
          <Minus size={13} className="text-indigo-400" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs text-indigo-400 font-medium mb-0.5">当前版本</div>
          <div className="text-sm text-white font-medium truncate">{data.title || data.doc_id}</div>
        </div>
        {data.version && <span className="text-xs text-indigo-300 font-mono shrink-0">v{data.version}</span>}
      </div>

      {data.older_versions.map(d => (
        <div key={d.id} className="flex items-center gap-3 px-4 py-3 bg-gray-900/40 border border-gray-800 rounded-xl opacity-70">
          <div className="w-7 h-7 rounded-lg bg-gray-800 border border-gray-700 flex items-center justify-center shrink-0">
            <ArrowDownRight size={13} className="text-gray-500" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs text-gray-600 font-medium mb-0.5">历史版本（已被替代）</div>
            <div className="text-sm text-gray-500 truncate">{d.title || d.id}</div>
          </div>
          {d.version && <span className="text-xs text-gray-700 font-mono shrink-0">v{d.version}</span>}
        </div>
      ))}

      {!data.newer_versions.length && !data.older_versions.length && (
        <div className="text-center py-8 text-gray-600 text-sm">该文档暂无已知版本链路</div>
      )}
    </div>
  );
}
