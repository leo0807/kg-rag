"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Upload, X, RotateCcw, Square, FileText, CheckCircle2, AlertCircle, Clock, Loader2 } from "lucide-react";
import { ApiError } from "@/lib/api";

type ItemStatus = "pending" | "uploading" | "done" | "skipped" | "error" | "interrupted";
interface FileItem {
    id: string;
    name: string;
    size: number;
    status: ItemStatus;
    file?: File;
    progress?: string;
    progressPct?: number;
    uploadedBytes?: number;
    docId?: string;
    sections?: number;
    error?: string;
}
interface PersistedItem { id: string; name: string; size: number; status: ItemStatus; docId?: string; sections?: number; error?: string; }
interface Stats { total: number; documents: number; sections: number; }
interface Props { onDone?: () => void; }

const SESSION_KEY = "ingest_session_v3";
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
        return parsed.map(p => ({
            ...p,
            // Guard against old session data that lacked these fields
            docId:    p.docId    ?? undefined,
            sections: p.sections ?? undefined,
        }));
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
    const [showErrors, setShowErrors] = useState(false);
    const [detailItem, setDetailItem] = useState<FileItem | null>(null);
    const abortRef  = useRef<AbortController | null>(null);
    const inputRef  = useRef<HTMLInputElement>(null);
    const startTimeRef = useRef<Record<string, number>>({});

    useEffect(() => {
        setItems(loadSession());
        fetch("/api/stats").then(r => r.json()).then(setStats).catch(() => {});
    }, []);

    useEffect(() => { if (items.length) saveSession(items); }, [items]);

    const addFiles = useCallback((newFiles: FileList | File[] | null) => {
        if (!newFiles) return;
        const fileArray = Array.from(newFiles).filter(f => {
            const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
            return ["pdf", "docx", "doc"].includes(ext);
        });
        if (!fileArray.length) return;
        setItems(prev => {
            const next = [...prev];
            fileArray.forEach(f => {
                const existing = next.find(it => it.name === f.name);
                if (existing) {
                    // Already ingested — don't duplicate; silently skip
                    if (existing.status === "done" || existing.status === "skipped") return;
                    // Re-attach file to interrupted / error / pending item
                    existing.file = f; existing.status = "pending"; existing.error = undefined;
                } else {
                    next.push({ id: uid(), name: f.name, size: f.size, status: "pending", file: f });
                }
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
    const retryFailed = () =>
        setItems(prev => prev.map(it => it.status === "error"
            ? { ...it, status: "pending", error: undefined }
            : it));

    const STEP_LABEL: Record<string, string> = {
        queued:      "排队中...",
        parsing:     "解析文档...",
        checking:    "检查已入库...",
        writing:     "写入图谱...",
        entities:    "提取实体...",
        constraints: "提取工艺约束...",
        tables:      "提取表格...",
        images:      "分析图片...",
    };

    const uploadOne = async (item: FileItem, signal: AbortSignal): Promise<boolean> => {
        if (signal.aborted || !item.file) return false;
        startTimeRef.current[item.id] = Date.now();
        setItems(prev => prev.map(it => it.id === item.id ? { ...it, status: "uploading", progress: "准备上传..." } : it));
        try {
            // ── 阶段 1：XHR 上传文件，保留上传进度条 ─────────────────────────
            const { task_id } = await new Promise<{ task_id: string }>((resolve, reject) => {
                const fd = new FormData();
                fd.append("file", item.file!);
                const token = localStorage.getItem("token") ?? "";
                const xhr = new XMLHttpRequest();
                xhr.open("POST", "/api/ingest", true);
                if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

                xhr.upload.onprogress = (e) => {
                    if (!e.lengthComputable) return;
                    const uploaded = e.loaded;
                    const total = e.total || item.size;
                    const elapsed = Math.max(1, (Date.now() - (startTimeRef.current[item.id] || Date.now())) / 1000);
                    const speed = uploaded / elapsed;
                    const eta = speed > 0 ? Math.round((total - uploaded) / speed) : null;
                    const pct = Math.min(100, Math.round((uploaded / total) * 100));
                    const etaText = eta !== null ? ` · 约 ${eta}s` : "";
                    setItems(prev => prev.map(it => it.id === item.id
                        ? { ...it, progress: `${pct}% · ${fmtSize(uploaded)}/${fmtSize(total)}${etaText}`, progressPct: pct, uploadedBytes: uploaded }
                        : it));
                };

                xhr.onerror = () => reject(new ApiError(0, "网络错误"));
                xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));
                xhr.onload = () => {
                    if (xhr.status < 200 || xhr.status >= 300) {
                        let message = `请求失败 (${xhr.status})`;
                        try {
                            const ct = xhr.getResponseHeader("content-type") ?? "";
                            const err = ct.includes("application/json")
                                ? JSON.parse(xhr.responseText || "{}") as { detail?: string | { msg: string }[] }
                                : null;
                            if (err?.detail) message = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
                            else if (xhr.responseText) message = xhr.responseText;
                        } catch { }
                        reject(new ApiError(xhr.status, message));
                        return;
                    }
                    try { resolve(JSON.parse(xhr.responseText)); }
                    catch { reject(new ApiError(xhr.status, "响应解析失败")); }
                };

                if (signal.aborted) xhr.abort();
                signal.addEventListener("abort", () => xhr.abort(), { once: true });
                xhr.send(fd);
            });

            // ── 阶段 2：轮询后台任务状态 ──────────────────────────────────────
            const token = localStorage.getItem("token") ?? "";
            const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

            while (true) {
                if (signal.aborted) return false;
                await new Promise(r => setTimeout(r, 2000));
                if (signal.aborted) return false;

                const sr = await fetch(`/api/ingest/status/${task_id}`, { headers, signal });
                if (!sr.ok) throw new ApiError(sr.status, await sr.text());
                const s = await sr.json() as { status: string; step: string; doc_id: string | null; sections: number; error: string | null };

                setItems(prev => prev.map(it => it.id === item.id
                    ? { ...it, progress: STEP_LABEL[s.step] ?? s.step, progressPct: undefined, uploadedBytes: undefined }
                    : it));

                if (s.status === "done" || s.status === "skipped") {
                    const st: ItemStatus = s.status === "skipped" ? "skipped" : "done";
                    setItems(prev => prev.map(it => it.id === item.id
                        ? { ...it, status: st, docId: s.doc_id ?? "", sections: s.sections, progress: "", progressPct: undefined, uploadedBytes: undefined }
                        : it));
                    return st === "done";
                }
                if (s.status === "error") {
                    throw new ApiError(500, s.error || "处理失败");
                }
            }
        } catch (e: unknown) {
            const interrupted = (e instanceof DOMException && e.name === "AbortError");
            setItems(prev => prev.map(it => it.id === item.id ? {
                ...it,
                status:       interrupted ? "interrupted" : "error",
                error:        interrupted ? undefined : (e instanceof ApiError ? e.message : "上传失败"),
                progress:     "",
                progressPct:  undefined,
                uploadedBytes: undefined,
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
    const firstError = items.find(it => it.status === "error" && it.error)?.error;
    const errorItems = items.filter(it => it.status === "error" && it.error);
    const canUpload = counts.pending > 0 && counts.pending > counts.noFile && !running;

    const totalBytes = items
        .filter(it => it.file)
        .reduce((sum, it) => sum + (it.size || 0), 0);
    const uploadedBytes = items.reduce((sum, it) => {
        if (it.status === "done" || it.status === "skipped") return sum + it.size;
        if (it.status === "uploading" && typeof it.uploadedBytes === "number") {
            return sum + it.uploadedBytes;
        }
        return sum;
    }, 0);
    const overallPct = totalBytes > 0 ? Math.min(100, Math.round((uploadedBytes / totalBytes) * 100)) : 0;
    const overallEta = (() => {
        const uploading = items.filter(it => it.status === "uploading" && it.uploadedBytes);
        if (!uploading.length) return null;
        const speeds = uploading.map(it => {
            const started = startTimeRef.current[it.id];
            const elapsed = started ? Math.max(1, (Date.now() - started) / 1000) : 1;
            return (it.uploadedBytes ?? 0) / elapsed;
        }).filter(s => s > 0);
        if (!speeds.length) return null;
        const speed = speeds.reduce((a, b) => a + b, 0);
        const remain = Math.max(0, totalBytes - uploadedBytes);
        return speed > 0 ? Math.round(remain / speed) : null;
    })();

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
                    <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-500 font-mono">DOC</span>
                    <span className="text-xs text-gray-600">支持同时选择多个文件</span>
                </div>
            </div>
            <input ref={inputRef} type="file" accept=".pdf,.docx,.doc" multiple className="hidden"
                onChange={e => { addFiles(e.target.files); e.target.value = ""; }} />

            {items.length > 0 && (
                <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span className="text-gray-600">共 {items.length} 个</span>
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
                        <div className="h-full bg-indigo-500 transition-all duration-300"
                            style={{ width: `${overallPct}%` }} />
                    </div>
                </div>
            )}

            {counts.error > 0 && (
                <div className="px-4 py-3 rounded-lg border border-red-800/60 bg-red-950/30 text-red-300 text-sm space-y-2">
                    <div className="flex items-start gap-2">
                        <AlertCircle size={16} className="mt-0.5 text-red-400 flex-shrink-0" />
                        <div className="min-w-0 flex-1">
                            <div className="font-medium">有 {counts.error} 个文件上传失败</div>
                            {firstError && (
                                <div className="text-xs text-red-400 mt-1 truncate">
                                    {firstError}
                                </div>
                            )}
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={retryFailed}
                                className="px-2.5 py-1 text-xs rounded border border-red-800 text-red-300 hover:bg-red-900/30 transition-colors"
                            >
                                重新上传失败项
                            </button>
                            <button
                                onClick={() => setShowErrors(v => !v)}
                                className="px-2.5 py-1 text-xs rounded border border-red-800 text-red-300 hover:bg-red-900/30 transition-colors"
                            >
                                {showErrors ? "收起详情" : "展开详情"}
                            </button>
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
                                    <div
                                        className="h-full bg-indigo-500 transition-all duration-200"
                                        style={{ width: `${item.progressPct ?? 0}%` }}
                                    />
                                </div>
                            )}
                        </div>
                                <div className="flex items-center gap-1.5 flex-shrink-0">
                                    {item.status === "error" && (
                                        <>
                                            <button onClick={() => setDetailItem(item)} title="查看详情"
                                                className="p-1 text-gray-500 hover:text-red-300 transition-colors">
                                                <AlertCircle size={13} />
                                            </button>
                                            <button onClick={() => retryItem(item.id)} title="重试"
                                                className="p-1 text-gray-500 hover:text-indigo-400 transition-colors">
                                                <RotateCcw size={13} />
                                            </button>
                                        </>
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
                            <button
                                onClick={() => { retryItem(detailItem.id); setDetailItem(null); }}
                                className="px-3 py-1.5 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-500 transition-colors"
                            >
                                重新上传
                            </button>
                            <button
                                onClick={() => setDetailItem(null)}
                                className="px-3 py-1.5 text-xs rounded border border-gray-700 text-gray-300 hover:bg-gray-900 transition-colors"
                            >
                                关闭
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
