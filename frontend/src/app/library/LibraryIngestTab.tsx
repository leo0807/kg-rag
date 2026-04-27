"use client";

import { useRef } from "react";
import { Upload, Square, Loader2, AlertCircle } from "lucide-react";
import { useIngest } from "./useIngest";
import { UploadDropzone } from "./UploadDropzone";
import { UploadProgress } from "./UploadProgress";

interface Props { onDone?: () => void; }

const CONCURRENCY = 3;

export function LibraryIngestTab({ onDone }: Props) {
    const inputRef = useRef<HTMLInputElement>(null);
    const {
        items, dragging, setDragging, stats, running,
        showErrors, setShowErrors, detailItem, setDetailItem,
        addFiles, removeItem, clearDone, clearAll, retryItem, retryFailed,
        uploadAll, abort, counts, totalBytes, uploadedBytes, overallPct, overallEta,
    } = useIngest(onDone);

    const canUpload = counts.pending > 0 && counts.pending > counts.noFile && !running;

    return (
        <div className="space-y-5">
            {stats && (
                <div className="flex gap-3">
                    {([["已入库文档", stats.documents], ["章节总数", stats.sections], ["图谱节点", stats.total]] as [string, number][]).map(([l, v]) => (
                        <div key={l} className="flex-1 px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg">
                            <div className="text-xs text-gray-500 mb-1">{l}</div>
                            <div className="text-xl font-semibold text-white">{v}</div>
                        </div>
                    ))}
                </div>
            )}

            <UploadDropzone
                dragging={dragging}
                running={running}
                onDragOver={() => setDragging(true)}
                onDragLeave={() => setDragging(false)}
                onDrop={(files) => { setDragging(false); addFiles(files); }}
                onBrowse={() => inputRef.current?.click()}
            />
            <input
                ref={inputRef} type="file" accept=".pdf,.docx,.doc" multiple className="hidden"
                onChange={e => { addFiles(e.target.files); e.target.value = ""; }}
            />

            <UploadProgress
                items={items} counts={counts}
                totalBytes={totalBytes} uploadedBytes={uploadedBytes}
                overallPct={overallPct} overallEta={overallEta}
                showErrors={showErrors} setShowErrors={setShowErrors}
                onRetryItem={retryItem} onRemoveItem={removeItem}
                onRetryFailed={retryFailed} onClearDone={clearDone}
                onClearAll={clearAll}
                onDetailItem={setDetailItem}
            />

            {(canUpload || running) && (
                <div className="flex items-center gap-3">
                    {!running && (
                        <button onClick={uploadAll}
                            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-500 transition-colors">
                            <Upload size={14} />
                            开始上传（{counts.pending - counts.noFile} 个文件）
                        </button>
                    )}
                    {running && (
                        <>
                            <div className="flex items-center gap-2 text-sm text-indigo-400">
                                <Loader2 size={14} className="animate-spin" />
                                <span>正在写入图谱...（最多 {CONCURRENCY} 个并行）</span>
                            </div>
                            <button onClick={abort}
                                className="flex items-center gap-1.5 px-3 py-2 border border-red-800 text-red-400 text-sm rounded-lg hover:bg-red-900/20 transition-colors">
                                <Square size={12} />中止
                            </button>
                        </>
                    )}
                </div>
            )}

            {detailItem && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60">
                    <div className="w-full max-w-lg mx-4 rounded-xl border border-gray-800 bg-gray-950 p-5 text-sm text-gray-200">
                        <div className="flex items-start gap-3">
                            <AlertCircle size={18} className="text-red-400 mt-0.5" />
                            <div className="min-w-0">
                                <div className="font-medium text-white">上传失败详情</div>
                                <div className="text-xs text-gray-400 mt-0.5">{detailItem.name}</div>
                            </div>
                        </div>
                        <div className="mt-3 rounded-lg border border-red-800/50 bg-red-950/30 p-3 text-red-300 text-xs whitespace-pre-wrap">
                            {detailItem.error || "未知错误"}
                        </div>
                        <div className="mt-4 flex items-center justify-end gap-2">
                            <button onClick={() => { retryItem(detailItem.id); setDetailItem(null); }}
                                className="px-3 py-1.5 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-500 transition-colors">重新上传</button>
                            <button onClick={() => setDetailItem(null)}
                                className="px-3 py-1.5 text-xs rounded border border-gray-700 text-gray-300 hover:bg-gray-900 transition-colors">关闭</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
