"use client";

import { useState, useRef } from "react";

interface IngestResult {
    doc_id: string;
    sections: number;
    status: string;
}

interface FileItem {
    file: File;
    status: "pending" | "uploading" | "done" | "error";
    result?: IngestResult;
    error?: string;
}

export default function IngestPage() {
    const [files, setFiles] = useState<FileItem[]>([]);
    const [dragging, setDragging] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    function addFiles(newFiles: FileList | null) {
        if (!newFiles) return;
        const items: FileItem[] = Array.from(newFiles)
            .filter(f => f.name.endsWith(".pdf"))
            .map(f => ({ file: f, status: "pending" }));
        setFiles(prev => [...prev, ...items]);
    }

    async function uploadAll() {
        for (let i = 0; i < files.length; i++) {
            if (files[i].status !== "pending") continue;

            // 更新状态为上传中
            setFiles(prev => prev.map((f, idx) =>
                idx === i ? { ...f, status: "uploading" } : f
            ));

            try {
                const fd = new FormData();
                fd.append("file", files[i].file);
                const res = await fetch("/api/ingest", { method: "POST", body: fd });
                const data = await res.json() as IngestResult;

                setFiles(prev => prev.map((f, idx) =>
                    idx === i ? { ...f, status: "done", result: data } : f
                ));
            } catch (e) {
                setFiles(prev => prev.map((f, idx) =>
                    idx === i ? { ...f, status: "error", error: "上传失败" } : f
                ));
            }
        }
    }

    const pendingCount = files.filter(f => f.status === "pending").length;

    return (
        <div className="p-8 min-h-screen bg-gray-950">
            <h1 className="text-2xl font-semibold text-white mb-6">导入文件</h1>

            {/* 拖拽区域 */}
            <div
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={e => {
                    e.preventDefault();
                    setDragging(false);
                    addFiles(e.dataTransfer.files);
                }}
                onClick={() => inputRef.current?.click()}
                className={`
          border-2 border-dashed rounded-xl p-12 text-center cursor-pointer
          transition-colors duration-200
          ${dragging
                        ? "border-indigo-500 bg-indigo-500/10"
                        : "border-gray-700 hover:border-gray-500 bg-gray-900"}
        `}
            >
                <div className="text-4xl mb-3">📄</div>
                <div className="text-gray-300 text-sm">
                    拖拽 PDF 文件到此处，或点击选择
                </div>
                <div className="text-gray-500 text-xs mt-1">
                    支持同时选择多个文件
                </div>
            </div>

            <input
                ref={inputRef}
                type="file"
                accept=".pdf"
                multiple
                className="hidden"
                onChange={e => addFiles(e.target.files)}
            />

            {/* 文件列表 */}
            {files.length > 0 && (
                <div className="mt-4 space-y-2">
                    {files.map((item, i) => (
                        <div key={i}
                            className="flex items-center gap-3 px-4 py-3 bg-gray-900
                         rounded-lg border border-gray-800">

                            <span className="text-lg">
                                {item.status === "done" ? "✅" :
                                    item.status === "error" ? "❌" :
                                        item.status === "uploading" ? "⏳" : "📄"}
                            </span>

                            <div className="flex-1 min-w-0">
                                <div className="text-sm text-gray-200 truncate">
                                    {item.file.name}
                                </div>
                                <div className="text-xs text-gray-500 mt-0.5">
                                    {item.status === "done" && item.result
                                        ? `${item.result.doc_id} · ${item.result.sections} 个章节`
                                        : item.status === "error"
                                            ? item.error
                                            : item.status === "uploading"
                                                ? "上传中..."
                                                : `${(item.file.size / 1024).toFixed(1)} KB`}
                                </div>
                            </div>

                            {item.status === "pending" && (
                                <button
                                    onClick={() => setFiles(prev => prev.filter((_, idx) => idx !== i))}
                                    className="text-gray-600 hover:text-gray-400 text-sm"
                                >✕</button>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* 上传按钮 */}
            {pendingCount > 0 && (
                <button
                    onClick={uploadAll}
                    className="mt-4 px-5 py-2 bg-indigo-600 text-white text-sm
                     rounded-lg hover:bg-indigo-500"
                >
                    上传 {pendingCount} 个文件并写入图谱
                </button>
            )}
        </div>
    );
}