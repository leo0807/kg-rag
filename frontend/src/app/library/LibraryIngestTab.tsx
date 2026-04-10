"use client";

import { useState, useRef, useEffect } from "react";
import { fetchApi, ApiError } from "@/lib/api";

interface IngestResult { doc_id: string; sections: number; status: string; message?: string; }
interface Stats { total: number; documents: number; sections: number; }
interface FileItem {
    file:      File;
    status:    "pending" | "uploading" | "done" | "skipped" | "error";
    result?:   IngestResult;
    error?:    string;
    progress?: string;
}

interface Props { onDone?: () => void; }

export function LibraryIngestTab({ onDone }: Props) {
    const [files,    setFiles]    = useState<FileItem[]>([]);
    const [dragging, setDragging] = useState(false);
    const [stats,    setStats]    = useState<Stats | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        fetch("/api/stats").then(r => r.json()).then(setStats).catch(() => {});
    }, []);

    function addFiles(newFiles: FileList | null) {
        if (!newFiles) return;
        const items: FileItem[] = Array.from(newFiles)
            .filter(f => f.name.endsWith(".pdf"))
            .map(f => ({ file: f, status: "pending" }));
        setFiles(prev => [...prev, ...items]);
    }

    async function uploadAll() {
        let doneCount = 0;
        let errorCount = 0;

        for (let i = 0; i < files.length; i++) {
            if (files[i].status !== "pending") continue;
            const clientId = `${Date.now()}_${i}`;
            const ws = new WebSocket(`ws://localhost:8000/ws/ingest/${clientId}`);
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                setFiles(prev => prev.map((f, idx) => idx === i ? { ...f, progress: data.detail } : f));
            };
            setFiles(prev => prev.map((f, idx) => idx === i ? { ...f, status: "uploading" } : f));
            try {
                const fd = new FormData();
                fd.append("file", files[i].file);
                const data = await fetchApi<IngestResult>(`/api/ingest?client_id=${clientId}`, { method: "POST", body: fd });
                ws.close();
                setFiles(prev => prev.map((f, idx) =>
                    idx === i ? { ...f, status: data.status === "skipped" ? "skipped" : "done", result: data, progress: "" } : f
                ));
                if (data.status !== "skipped") doneCount++;
            } catch (e) {
                ws.close();
                const message = e instanceof ApiError ? e.message : "上传失败";
                setFiles(prev => prev.map((f, idx) => idx === i ? { ...f, status: "error", error: message, progress: "" } : f));
                errorCount++;
            }
        }

        if (errorCount === 0 && doneCount > 0) {
            fetch("/api/stats").then(r => r.json()).then(setStats).catch(() => {});
            setTimeout(() => { setFiles([]); onDone?.(); }, 1500);
        }
    }

    const pendingCount = files.filter(f => f.status === "pending").length;

    return (
        <div className="max-w-2xl space-y-5">
            {/* 统计卡片 */}
            {stats && (
                <div className="flex gap-3">
                    {[
                        { label: "已入库文档", value: stats.documents },
                        { label: "章节总数",   value: stats.sections  },
                        { label: "图谱节点",   value: stats.total     },
                    ].map(({ label, value }) => (
                        <div key={label} className="flex-1 px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg">
                            <div className="text-xs text-gray-500 mb-1">{label}</div>
                            <div className="text-2xl font-semibold text-white">{value}</div>
                        </div>
                    ))}
                </div>
            )}

            {/* 拖拽区域 */}
            <div
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
                onClick={() => inputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors duration-200
                    ${dragging ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 hover:border-gray-500 bg-gray-900"}`}
            >
                <div className="text-4xl mb-3">📄</div>
                <div className="text-gray-300 text-sm">拖拽 PDF 文件到此处，或点击选择</div>
                <div className="text-gray-500 text-xs mt-1">支持同时选择多个文件</div>
            </div>
            <input ref={inputRef} type="file" accept=".pdf" multiple className="hidden" onChange={e => addFiles(e.target.files)} />

            {/* 文件列表 */}
            {files.length > 0 && (
                <div className="space-y-2">
                    {files.map((item, i) => (
                        <div key={i} className="flex items-center gap-3 px-4 py-3 bg-gray-900 rounded-lg border border-gray-800">
                            <span className="text-lg">
                                {item.status === "done" ? "✅" : item.status === "skipped" ? "⏭️" :
                                 item.status === "error" ? "❌" : item.status === "uploading" ? "⏳" : "📄"}
                            </span>
                            <div className="flex-1 min-w-0">
                                <div className="text-sm text-gray-200 truncate">{item.file.name}</div>
                                <div className="text-xs text-gray-500 mt-0.5">
                                    {item.status === "done" && item.result
                                        ? `${item.result.doc_id} · ${item.result.sections} 个章节`
                                        : item.status === "skipped" && item.result
                                            ? `${item.result.doc_id} · 已入库，跳过`
                                            : item.status === "error" ? item.error
                                            : item.status === "uploading" ? (item.progress || "上传中...")
                                            : `${(item.file.size / 1024).toFixed(1)} KB`}
                                </div>
                            </div>
                            {item.status === "pending" && (
                                <button onClick={() => setFiles(prev => prev.filter((_, idx) => idx !== i))}
                                    className="text-gray-600 hover:text-gray-400 text-sm">✕</button>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* 上传按钮 */}
            {pendingCount > 0 && (
                <button onClick={uploadAll}
                    className="px-5 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500">
                    上传 {pendingCount} 个文件并写入图谱
                </button>
            )}
        </div>
    );
}
