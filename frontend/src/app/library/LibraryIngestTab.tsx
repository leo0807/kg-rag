"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Upload, X, RotateCcw, Square, FileText, CheckCircle2, AlertCircle, Clock, Loader2 } from "lucide-react";
import { ApiError } from "@/lib/api";

type ItemStatus = "pending" | "uploading" | "done" | "skipped" | "error" | "interrupted";
interface FileItem { id: string; name: string; size: number; status: ItemStatus; file?: File; progress?: string; docId?: string; sections?: number; error?: string; }
interface PersistedItem { id: string; name: string; size: number; status: ItemStatus; docId?: string; sections?: number; error?: string; }
interface Stats { total: number; documents: number; sections: number; }
interface Props { onDone?: () => void; }

const SESSION_KEY = "ingest_session_v2";
const CONCURRENCY = 3;

function saveSession(items: FileItem[]) {
    const persisted: PersistedItem[] = items.map(({ id, name, size, status, docId, sections, error }) => ({
        id, name, size,
        status: status === "uploading" ? "interrupted" : status,
        docId, sections, error,
    }));
    localStorage.setItem(SESSION_KEY, JSON.stringify(persisted));
}

function loadSession(): FileItem[] {
    try {
        const raw = localStorage.getItem(SESSION_KEY);
        if (!raw) return [];
        const parsed: PersistedItem[] = JSON.parse(raw);
        return parsed.map(p => ({ ...p }));
    } catch { return []; }
}

function uid() { return Math.random().toString(36).slice(2, 10); }
function fmtSize(b: number) { return b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${(b / 1024).toFixed(1)} KB`; }

const STATUS_ICON: Record<ItemStatus, React.ReactNode> = {
    done:        <CheckCircle2 size={14} className="text-emerald-400" />,
    skipped:     <CheckCircle2 size={14} className="text-gray-500" />,
    error:       <AlertCircle  size={14} className="text-red-400" />,
    interrupted: <Clock        size={14} className="text-amber-400" />,
    uploading:   <Loader2      size={14} className="text-indigo-400 animate-spin" />,
    pending:     <FileText     size={14} className="text-gray-400" />,
};


export function LibraryIngestTab({ onDone }: Props) {
    const [items,    setItems]    = useState<FileItem[]>([]);
    const [dragging, setDragging] = useState(false);
    const [stats,    setStats]    = useState<Stats | null>(null);
    const [running,  setRunning]  = useState(false);
    const abortRef  = useRef<AbortController | null>(null);
    const inputRef  = useRef<HTMLInputElement>(null);

    useEffect(() => {
        setItems(loadSession());
        fetch("/api/stats").then(r => r.json()).then(setStats).catch(() => {});
    }, []);

    useEffect(() => { if (items.length) saveSession(items); }, [items]);

    const addFiles = useCallback((newFiles: FileList | File[] | null) => {
        if (!newFiles) return;
        const fileArray = Array.from(newFiles).filter(f => {
            const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
            return ["pdf", "docx"].includes(ext);
        });
        if (!fileArray.length) return;
        setItems(prev => {
            const next = [...prev];
            fileArray.forEach(f => {
                const existing = next.find(it => it.name === f.name &&
                    (it.status === "interrupted" || it.status === "error" || it.status === "pending"));
                if (existing) { existing.file = f; existing.status = "pending"; existing.error = undefined; }
                else next.push({ id: uid(), name: f.name, size: f.size, status: "pending", file: f });
            });
            return next;
        });
    }, []);

    const removeItem = (id: string) => setItems(prev => prev.filter(it => it.id !== id));
    const clearDone = () => setItems(prev => {
        const next = prev.filter(it => it.status !== "done" && it.status !== "skipped");
        if (!next.length) localStorage.removeItem(SESSION_KEY);
        return next;
    });
    const retryItem = (id: string) =>
        setItems(prev => prev.map(it => it.id === id ? { ...it, status: "pending", error: undefined } : it));

    const uploadOne = async (item: FileItem, signal: AbortSignal): Promise<boolean> => {
        if (signal.aborted || !item.file) return false;
        setItems(prev => prev.map(it => it.id === item.id ? { ...it, status: "uploading", progress: "" } : it));
        try {
            const fd = new FormData();
            fd.append("file", item.file);
            const token = localStorage.getItem("token") ?? "";
            const res = await fetch("/api/ingest", {
                method: "POST", body: fd, signal,
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
            if (!res.ok) throw new ApiError(res.status, await res.text());
            const data = await res.json();
            const st: ItemStatus = data.status === "skipped" ? "skipped" : "done";
            setItems(prev => prev.map(it => it.id === item.id
                ? { ...it, status: st, docId: data.doc_id, sections: data.sections, progress: "" } : it));
            return st === "done";
        } catch (e: unknown) {
            const interrupted = (e instanceof DOMException && e.name === "AbortError");
            setItems(prev => prev.map(it => it.id === item.id ? {
                ...it,
                status:   interrupted ? "interrupted" : "error",
                error:    interrupted ? undefined : (e instanceof ApiError ? e.message : "上传失败"),
                progress: "",
            } : it));
            return false;
        }
    };

    const uploadAll = async () => {
        setRunning(true);
        abortRef.current = new AbortController();
        const { signal } = abortRef.current;

        // Snapshot pending items at start
        const queue = items.filter(it => it.status === "pending" && it.file);
        let idx = 0;
        let doneCount = 0;

        const worker = async () => {
            while (true) {
                if (signal.aborted) break;
                const i = idx++;
                if (i >= queue.length) break;
                const ok = await uploadOne(queue[i], signal);
                if (ok) doneCount++;
            }
        };

        await Promise.all(Array.from({ length: Math.min(CONCURRENCY, queue.length) }, worker));

        setRunning(false);
        abortRef.current = null;
        if (doneCount > 0) {
            fetch("/api/stats").then(r => r.json()).then(setStats).catch(() => {});
            onDone?.();
        }
    };

    const abort = () => { abortRef.current?.abort(); };

    const counts = {
        pending:     items.filter(it => it.status === "pending").length,
        uploading:   items.filter(it => it.status === "uploading").length,
        done:        items.filter(it => it.status === "done" || it.status === "skipped").length,
        error:       items.filter(it => it.status === "error").length,
        interrupted: items.filter(it => it.status === "interrupted").length,
        noFile:      items.filter(it => (it.status === "pending" || it.status === "interrupted") && !it.file).length,
    };
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

            <div
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
                onClick={() => !running && inputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl text-center transition-colors duration-200
                    ${items.length ? "py-4" : "py-10"}
                    ${dragging ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 hover:border-gray-600 bg-gray-900/60"}
                    ${running ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
            >
                <Upload size={22} className={`mx-auto mb-2 ${dragging ? "text-indigo-400" : "text-gray-500"}`} />
                <div className="text-gray-200 text-sm font-medium">
                    {dragging ? "松开以添加文件" : "拖拽文件到此处，或点击选择"}
                </div>
                <div className="flex items-center justify-center gap-3 mt-2">
                    <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-500 font-mono">PDF</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-500 font-mono">DOCX</span>
                    <span className="text-xs text-gray-600">支持同时选择多个文件</span>
                </div>
            </div>
            <input ref={inputRef} type="file" accept=".pdf,.docx" multiple className="hidden"
                onChange={e => { addFiles(e.target.files); e.target.value = ""; }} />

            {items.length > 0 && (
                <div className="flex items-center gap-4 text-xs text-gray-500">
                    {counts.pending > 0    && <span className="text-gray-300">{counts.pending} 待上传</span>}
                    {counts.uploading > 0  && <span className="text-indigo-400 flex items-center gap-1"><Loader2 size={11} className="animate-spin" />{counts.uploading} 上传中</span>}
                    {counts.done > 0       && <span className="text-emerald-400">{counts.done} 已完成</span>}
                    {counts.interrupted > 0 && <span className="text-amber-400">{counts.interrupted} 已中断</span>}
                    {counts.error > 0      && <span className="text-red-400">{counts.error} 失败</span>}
                    {counts.noFile > 0     && <span className="text-amber-400">↑ {counts.noFile} 项需重新选择文件</span>}
                    <span className="flex-1" />
                    {counts.done > 0 && <button onClick={clearDone} className="text-gray-600 hover:text-gray-300 transition-colors">清除完成项</button>}
                    <button onClick={() => { setItems([]); localStorage.removeItem(SESSION_KEY); }}
                        className="text-gray-600 hover:text-red-400 transition-colors">清空全部</button>
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
                                        {item.status === "done"        && `${item.docId} · ${item.sections} 个章节`}
                                        {item.status === "skipped"     && `${item.docId} · 已入库，跳过`}
                                        {item.status === "error"       && <span className="text-red-400">{item.error}</span>}
                                        {item.status === "interrupted" && <span className="text-amber-400">已中断，可重新上传</span>}
                                        {item.status === "pending"     && fmtSize(item.size)}
                                    </div>
                                </div>
                                <div className="flex items-center gap-1.5 flex-shrink-0">
                                    {item.status === "error" && (
                                        <button onClick={() => retryItem(item.id)} title="重试"
                                            className="p-1 text-gray-500 hover:text-indigo-400 transition-colors">
                                            <RotateCcw size={13} />
                                        </button>
                                    )}
                                    {(item.status === "pending" || item.status === "interrupted" || item.status === "error") && (
                                        <button onClick={() => removeItem(item.id)} title="移除"
                                            className="p-1 text-gray-600 hover:text-red-400 transition-colors">
                                            <X size={13} />
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

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
        </div>
    );
}
