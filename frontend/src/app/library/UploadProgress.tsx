"use client";

import { CheckCircle2, AlertCircle, Clock, Loader2, FileText, RotateCcw, X } from "lucide-react";
import type { FileItem, ItemStatus } from "./useIngest";
import { fmtSize } from "./useIngest";

const STATUS_ICON: Record<ItemStatus, React.ReactNode> = {
    done:        <CheckCircle2 size={14} className="text-emerald-400" />,
    skipped:     <CheckCircle2 size={14} className="text-gray-500" />,
    error:       <AlertCircle  size={14} className="text-red-400" />,
    interrupted: <Clock        size={14} className="text-amber-400" />,
    uploading:   <Loader2      size={14} className="text-indigo-400 animate-spin" />,
    pending:     <FileText     size={14} className="text-gray-400" />,
};

interface Props {
    items: FileItem[];
    counts: { pending: number; uploading: number; done: number; error: number; interrupted: number; noFile: number };
    totalBytes: number;
    uploadedBytes: number;
    overallPct: number;
    overallEta: number | null;
    showErrors: boolean;
    setShowErrors: (v: boolean) => void;
    onRetryItem: (id: string) => void;
    onRemoveItem: (id: string) => void;
    onRetryFailed: () => void;
    onClearDone: () => void;
    onClearAll: () => void;
    onDetailItem: (item: FileItem) => void;
}

export function UploadProgress({
    items, counts, totalBytes, uploadedBytes, overallPct, overallEta,
    showErrors, setShowErrors, onRetryItem, onRemoveItem, onRetryFailed, onClearDone, onClearAll, onDetailItem,
}: Props) {
    const firstError  = items.find(it => it.status === "error" && it.error)?.error;
    const errorItems  = items.filter(it => it.status === "error" && it.error);

    return (
        <div className="space-y-4">
            {items.length > 0 && (
                <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span className="text-gray-600">共 {items.length} 个</span>
                    {counts.pending > 0     && <span className="text-gray-300">{counts.pending} 待上传</span>}
                    {counts.uploading > 0   && <span className="text-indigo-400 flex items-center gap-1"><Loader2 size={11} className="animate-spin" />{counts.uploading} 上传中</span>}
                    {counts.done > 0        && <span className="text-emerald-400">{counts.done} 已完成</span>}
                    {counts.interrupted > 0 && <span className="text-amber-400">{counts.interrupted} 已中断</span>}
                    {counts.error > 0       && <span className="text-red-400">{counts.error} 失败</span>}
                    {counts.noFile > 0      && <span className="text-amber-400">↑ {counts.noFile} 项需重新选择文件</span>}
                    <span className="flex-1" />
                    {counts.done > 0 && <button onClick={onClearDone} className="text-gray-600 hover:text-gray-300 transition-colors">清除完成项</button>}
                    <button onClick={onClearAll} className="text-gray-600 hover:text-red-400 transition-colors">清空全部</button>
                </div>
            )}

            {items.length > 0 && totalBytes > 0 && (
                <div className="px-4 py-3 rounded-lg border border-gray-800 bg-gray-950 space-y-2">
                    <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>整体进度</span>
                        <span className="text-gray-400">
                            {overallPct}% · {fmtSize(uploadedBytes)}/{fmtSize(totalBytes)}
                            {overallEta !== null ? ` · 约 ${overallEta}s` : ""}
                        </span>
                    </div>
                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                        <div className="h-full bg-indigo-500 transition-all duration-300" style={{ width: `${overallPct}%` }} />
                    </div>
                </div>
            )}

            {counts.error > 0 && (
                <div className="px-4 py-3 rounded-lg border border-red-800/60 bg-red-950/30 text-red-300 text-sm space-y-2">
                    <div className="flex items-start gap-2">
                        <AlertCircle size={16} className="mt-0.5 text-red-400 flex-shrink-0" />
                        <div className="min-w-0 flex-1">
                            <div className="font-medium">有 {counts.error} 个文件上传失败</div>
                            {firstError && <div className="text-xs text-red-400 mt-1 truncate">{firstError}</div>}
                        </div>
                        <div className="flex items-center gap-2">
                            <button onClick={onRetryFailed} className="px-2.5 py-1 text-xs rounded border border-red-800 text-red-300 hover:bg-red-900/30 transition-colors">重新上传失败项</button>
                            <button onClick={() => setShowErrors(!showErrors)} className="px-2.5 py-1 text-xs rounded border border-red-800 text-red-300 hover:bg-red-900/30 transition-colors">{showErrors ? "收起详情" : "展开详情"}</button>
                        </div>
                    </div>
                    {showErrors && errorItems.length > 0 && (
                        <div className="grid gap-1">
                            {errorItems.map(it => (
                                <div key={it.id} className="flex items-center gap-2 text-xs text-red-300">
                                    <span className="truncate flex-1">{it.name}</span>
                                    <span className="truncate text-red-400 max-w-[50%]">{it.error}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {items.length > 0 && (
                <div className="border border-gray-800 rounded-xl overflow-hidden">
                    <div className="divide-y divide-gray-800/60 max-h-96 overflow-y-auto">
                        {items.map(item => (
                            <div key={item.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-900/50">
                                <span className="flex-shrink-0">{STATUS_ICON[item.status]}</span>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-2">
                                        <span className="text-sm text-gray-200 truncate">{item.name}</span>
                                        {!item.file && (item.status === "pending" || item.status === "interrupted") && (
                                            <span className="text-xs px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400 flex-shrink-0">需重选文件</span>
                                        )}
                                    </div>
                                    <div className="text-xs text-gray-500 mt-0.5">
                                        {item.status === "uploading"   && (item.progress || "上传中...")}
                                        {item.status === "done"        && `${item.docId || "—"} · ${item.sections ?? "?"} 个章节`}
                                        {item.status === "skipped"     && `${item.docId || "—"} · 已入库，跳过`}
                                        {item.status === "error"       && <span className="text-red-400">{item.error}</span>}
                                        {item.status === "interrupted" && <span className="text-amber-400">已中断，可重新上传</span>}
                                        {item.status === "pending"     && fmtSize(item.size)}
                                    </div>
                                    {item.status === "uploading" && (
                                        <div className="mt-2 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                            <div className="h-full bg-indigo-500 transition-all duration-200" style={{ width: `${item.progressPct ?? 0}%` }} />
                                        </div>
                                    )}
                                </div>
                                <div className="flex items-center gap-1.5 flex-shrink-0">
                                    {item.status === "error" && (
                                        <>
                                            <button onClick={() => onDetailItem(item)} title="查看详情" className="p-1 text-gray-500 hover:text-red-300 transition-colors"><AlertCircle size={13} /></button>
                                            <button onClick={() => onRetryItem(item.id)} title="重试" className="p-1 text-gray-500 hover:text-indigo-400 transition-colors"><RotateCcw size={13} /></button>
                                        </>
                                    )}
                                    {(item.status === "pending" || item.status === "interrupted" || item.status === "error") && (
                                        <button onClick={() => onRemoveItem(item.id)} title="移除" className="p-1 text-gray-600 hover:text-red-400 transition-colors"><X size={13} /></button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
