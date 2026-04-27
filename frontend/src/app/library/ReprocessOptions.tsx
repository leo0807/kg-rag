"use client";

import {
  AlertTriangle, BookOpen, Check, CheckSquare, FileSearch, Image, Loader2,
  RefreshCw, RotateCcw, Search, Sliders, Square, Table, Trash2, Square as StopIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { PIPELINES, type Doc, type PK } from "./useReprocess";

const PIPELINE_ICONS: Record<string, ReactNode> = {
  reparse:     <BookOpen size={13} />,
  images:      <Image size={13} />,
  entities:    <FileSearch size={13} />,
  constraints: <Sliders size={13} />,
  tables:      <Table size={13} />,
  drawings:    <Search size={13} />,
  defects:     <AlertTriangle size={13} />,
};

interface Props {
  sel: Set<PK>;
  setSel: (fn: (prev: Set<PK>) => Set<PK>) => void;
  docs: Doc[];
  docsLoading: boolean;
  docSearch: string;
  setDocSearch: (s: string) => void;
  selectedDocs: Set<string>;
  filteredDocs: Doc[];
  allSelected: boolean;
  someSelected: boolean;
  isRunning: boolean;
  isDone: boolean;
  canResume: boolean;
  busy: boolean;
  confirm: boolean;
  setConfirm: (v: boolean) => void;
  toggleDoc: (id: string) => void;
  toggleAll: () => void;
  clearSelection: () => void;
  start: () => void;
  cancel: () => void;
  resume: () => void;
  clearBatch: () => void;
}

export function ReprocessOptions({
  sel, setSel, docs, docsLoading, docSearch, setDocSearch,
  selectedDocs, filteredDocs, allSelected, someSelected,
  isRunning, isDone, canResume, busy, confirm, setConfirm,
  toggleDoc, toggleAll, clearSelection, start, cancel, resume, clearBatch,
}: Props) {
  return (
    <div className="space-y-4">
      {/* 文档选择面板 */}
      <div className="bg-gray-950 border border-gray-800 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs text-gray-500 uppercase tracking-wider">
            选择待处理文档
            {someSelected
              ? <span className="ml-2 text-indigo-400 normal-case">已选 {selectedDocs.size} 个</span>
              : <span className="ml-2 text-gray-600 normal-case">（未选则处理全部 {docs.length} 个）</span>
            }
          </span>
          <button onClick={clearSelection} disabled={!someSelected}
            className="text-xs text-gray-500 hover:text-gray-300 disabled:opacity-30 transition-colors">
            清除选择
          </button>
        </div>

        <div className="relative mb-2">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
          <input value={docSearch} onChange={e => setDocSearch(e.target.value)}
            placeholder="搜索规范编号或标题..."
            className="w-full pl-7 pr-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-xs
                       text-gray-200 outline-none focus:border-indigo-500 placeholder-gray-600" />
        </div>

        <div className="flex items-center gap-2 px-2 py-1.5 border-b border-gray-800 mb-1">
          <button onClick={toggleAll} className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-200 transition-colors">
            {allSelected ? <CheckSquare size={13} className="text-indigo-400" /> : <Square size={13} />}
            {allSelected ? "取消全选" : "全选当前"}
            {filteredDocs.length !== docs.length && (
              <span className="text-gray-600">({filteredDocs.length} 个)</span>
            )}
          </button>
        </div>

        <div className="max-h-[300px] overflow-y-auto">
          {docsLoading ? (
            <div className="flex items-center gap-2 py-4 justify-center text-xs text-gray-500">
              <Loader2 size={12} className="animate-spin" />加载中...
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="py-4 text-center text-xs text-gray-600">无匹配文档</div>
          ) : filteredDocs.map((doc, idx) => (
            <label key={doc.doc_id}
              className={`flex items-center gap-2.5 px-2 py-1.5 cursor-pointer transition-colors
                ${selectedDocs.has(doc.doc_id)
                  ? "bg-indigo-900/20 border-l-2 border-indigo-500"
                  : idx % 2 === 0 ? "bg-gray-900/40 border-l-2 border-transparent" : "border-l-2 border-transparent"}
                ${isRunning ? "pointer-events-none opacity-50" : "hover:bg-indigo-900/10"}`}>
              <input type="checkbox" className="accent-indigo-500 shrink-0"
                checked={selectedDocs.has(doc.doc_id)} disabled={isRunning}
                onChange={() => toggleDoc(doc.doc_id)} />
              <span className="font-mono text-xs text-indigo-400 shrink-0 w-20">{doc.doc_id}</span>
              <span className="text-xs text-gray-300 flex-1 truncate min-w-0">{doc.title ?? "—"}</span>
              <span className={`text-xs shrink-0 tabular-nums ml-2 ${doc.section_count === 0 ? "text-red-500" : "text-gray-500"}`}>
                {doc.section_count} 章
              </span>
            </label>
          ))}
        </div>
      </div>

      {/* 管道选择 */}
      <div className="bg-gray-950 border border-gray-800 rounded-xl p-4">
        <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">处理管道</div>
        <div className="grid grid-cols-2 gap-2 mb-4">
          {PIPELINES.map(({ key, label, desc }) => {
            const checked = sel.has(key);
            return (
              <label key={key}
                className={`relative flex items-start gap-2.5 px-3 py-2.5 rounded-lg border cursor-pointer transition-all select-none
                  ${checked ? "border-indigo-500 bg-indigo-900/20" : "border-gray-700 bg-gray-900/60 hover:border-gray-500"}
                  ${isRunning ? "opacity-50 pointer-events-none" : ""}`}>
                <input type="checkbox" className="hidden"
                  checked={checked} disabled={isRunning}
                  onChange={() => setSel(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n; })} />
                <span className={`mt-0.5 shrink-0 ${checked ? "text-indigo-400" : "text-gray-500"}`}>
                  {PIPELINE_ICONS[key]}
                </span>
                <div className="min-w-0 flex-1">
                  <div className={`text-xs font-medium ${checked ? "text-indigo-200" : "text-gray-300"}`}>{label}</div>
                  <div className="text-[11px] text-gray-500 truncate">{desc}</div>
                </div>
                {checked && (
                  <span className="absolute top-1.5 right-1.5 text-indigo-400">
                    <Check size={10} strokeWidth={3} />
                  </span>
                )}
              </label>
            );
          })}
        </div>

        {/* 选择摘要 */}
        <p className="text-xs text-gray-500 mb-3">
          将对&nbsp;<span className="text-indigo-400 font-medium">
            {someSelected ? `${selectedDocs.size} 份` : `全部 ${docs.length} 份`}
          </span>&nbsp;文档执行&nbsp;<span className="text-indigo-400 font-medium">{sel.size} 个</span>&nbsp;处理管道
        </p>

        {/* 主操作按钮 */}
        <button onClick={() => setConfirm(true)} disabled={isRunning || busy || sel.size === 0}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium
                     bg-[#005bac] text-white hover:bg-[#004d93] disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
          {isRunning
            ? <><Loader2 size={14} className="animate-spin" />处理中...</>
            : busy
              ? <><Loader2 size={14} className="animate-spin" />启动中...</>
              : <><RefreshCw size={14} />批量处理</>
          }
        </button>

        {/* 次级操作 */}
        {(canResume || isDone) && (
          <div className="flex gap-2 mt-2">
            {canResume && (
              <button onClick={resume} disabled={busy}
                className="flex-1 py-2 rounded-lg text-xs font-medium border border-indigo-600 text-indigo-300
                           hover:bg-indigo-900/30 disabled:opacity-50 transition-colors flex items-center justify-center gap-1.5">
                <RotateCcw size={12} />续跑
              </button>
            )}
            {isDone && (
              <button onClick={clearBatch}
                className="flex-1 py-2 rounded-lg text-xs font-medium border border-gray-700 text-gray-400
                           hover:bg-gray-800 transition-colors flex items-center justify-center gap-1.5">
                <Trash2 size={12} />清除记录
              </button>
            )}
          </div>
        )}
        {isRunning && (
          <button onClick={cancel}
            className="w-full mt-2 py-2 rounded-lg text-xs font-medium border border-red-700/60 text-red-400
                       hover:bg-red-900/20 transition-colors flex items-center justify-center gap-1.5">
            <StopIcon size={12} />中止任务
          </button>
        )}
      </div>

      {/* 确认弹窗 */}
      {confirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setConfirm(false)}>
          <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 w-96 shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <h2 className="text-base font-semibold text-white mb-2">确认批量重新处理？</h2>
            <p className="text-sm text-gray-400 mb-1">
              {someSelected ? `将对选中的 ${selectedDocs.size} 个文档依次运行：` : `将对全部 ${docs.length} 个文档依次运行：`}
            </p>
            <ul className="text-sm text-indigo-300 mb-4 list-disc list-inside space-y-0.5">
              {[...sel].map(k => <li key={k}>{PIPELINES.find(p => p.key === k)?.label}</li>)}
            </ul>
            <p className="text-xs text-gray-500 mb-5">处理前将自动拍摄快照，可随时中止。</p>
            <div className="flex gap-3">
              <button onClick={() => setConfirm(false)}
                className="flex-1 py-2 rounded-lg border border-gray-700 text-sm text-gray-400 hover:text-white transition-colors">
                取消
              </button>
              <button onClick={start}
                className="flex-1 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 transition-colors">
                确认开始
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
