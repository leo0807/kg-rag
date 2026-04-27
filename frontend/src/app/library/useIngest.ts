"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { ApiError } from "@/lib/api";

export type ItemStatus = "pending" | "uploading" | "done" | "skipped" | "error" | "interrupted";

export interface FileItem {
    id: string; name: string; size: number; status: ItemStatus;
    file?: File; progress?: string; progressPct?: number;
    uploadedBytes?: number; docId?: string; sections?: number; error?: string;
}

interface PersistedItem {
    id: string; name: string; size: number; status: ItemStatus;
    docId?: string; sections?: number; error?: string;
}

export interface Stats { total: number; documents: number; sections: number; }

const SESSION_KEY = "ingest_session_v3";
const CONCURRENCY = 3;

const STEP_LABEL: Record<string, string> = {
    queued: "排队中...", parsing: "解析文档...", checking: "检查已入库...",
    writing: "写入图谱...", entities: "提取实体...", constraints: "提取工艺约束...",
    tables: "提取表格...", images: "分析图片...",
};

function saveSession(items: FileItem[]) {
    const persisted: PersistedItem[] = items.map(({ id, name, size, status, docId, sections, error }) => ({
        id, name, size, status: status === "uploading" ? "interrupted" : status, docId, sections, error,
    }));
    localStorage.setItem(SESSION_KEY, JSON.stringify(persisted));
}

function loadSession(): FileItem[] {
    try {
        const raw = localStorage.getItem(SESSION_KEY);
        if (!raw) return [];
        const parsed: PersistedItem[] = JSON.parse(raw);
        return parsed.map(p => ({ ...p, docId: p.docId ?? undefined, sections: p.sections ?? undefined }));
    } catch { return []; }
}

export function uid() { return Math.random().toString(36).slice(2, 10); }
export function fmtSize(b: number) { return b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${(b / 1024).toFixed(1)} KB`; }

export function useIngest(onDone?: () => void) {
    const [items,      setItems]      = useState<FileItem[]>([]);
    const [dragging,   setDragging]   = useState(false);
    const [stats,      setStats]      = useState<Stats | null>(null);
    const [running,    setRunning]    = useState(false);
    const [showErrors, setShowErrors] = useState(false);
    const [detailItem, setDetailItem] = useState<FileItem | null>(null);
    const abortRef    = useRef<AbortController | null>(null);
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
                    if (existing.status === "done" || existing.status === "skipped") return;
                    existing.file = f; existing.status = "pending"; existing.error = undefined;
                } else {
                    next.push({ id: uid(), name: f.name, size: f.size, status: "pending", file: f });
                }
            });
            return next;
        });
    }, []);

    const removeItem  = (id: string) => setItems(prev => prev.filter(it => it.id !== id));
    const clearAll    = () => { setItems([]); localStorage.removeItem(SESSION_KEY); };
    const clearDone   = () => setItems(prev => {
        const next = prev.filter(it => it.status !== "done" && it.status !== "skipped");
        if (!next.length) localStorage.removeItem(SESSION_KEY);
        return next;
    });
    const retryItem   = (id: string) =>
        setItems(prev => prev.map(it => it.id === id ? { ...it, status: "pending", error: undefined } : it));
    const retryFailed = () =>
        setItems(prev => prev.map(it => it.status === "error" ? { ...it, status: "pending", error: undefined } : it));

    const uploadOne = async (item: FileItem, signal: AbortSignal): Promise<boolean> => {
        if (signal.aborted || !item.file) return false;
        startTimeRef.current[item.id] = Date.now();
        setItems(prev => prev.map(it => it.id === item.id ? { ...it, status: "uploading", progress: "准备上传..." } : it));
        try {
            const { task_id } = await new Promise<{ task_id: string }>((resolve, reject) => {
                const fd = new FormData();
                fd.append("file", item.file!);
                const token = localStorage.getItem("token") ?? "";
                const xhr = new XMLHttpRequest();
                xhr.open("POST", "/api/ingest", true);
                if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
                xhr.upload.onprogress = (e) => {
                    if (!e.lengthComputable) return;
                    const uploaded = e.loaded, total = e.total || item.size;
                    const elapsed = Math.max(1, (Date.now() - (startTimeRef.current[item.id] || Date.now())) / 1000);
                    const speed = uploaded / elapsed;
                    const eta = speed > 0 ? Math.round((total - uploaded) / speed) : null;
                    const pct = Math.min(100, Math.round((uploaded / total) * 100));
                    setItems(prev => prev.map(it => it.id === item.id
                        ? { ...it, progress: `${pct}% · ${fmtSize(uploaded)}/${fmtSize(total)}${eta !== null ? ` · 约 ${eta}s` : ""}`, progressPct: pct, uploadedBytes: uploaded }
                        : it));
                };
                xhr.onerror = () => reject(new ApiError(0, "网络错误"));
                xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));
                xhr.onload = () => {
                    if (xhr.status < 200 || xhr.status >= 300) {
                        let message = `请求失败 (${xhr.status})`;
                        try {
                            const ct = xhr.getResponseHeader("content-type") ?? "";
                            const err = ct.includes("application/json") ? JSON.parse(xhr.responseText || "{}") as { detail?: string | { msg: string }[] } : null;
                            if (err?.detail) message = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
                            else if (xhr.responseText) message = xhr.responseText;
                        } catch { }
                        reject(new ApiError(xhr.status, message)); return;
                    }
                    try { resolve(JSON.parse(xhr.responseText)); }
                    catch { reject(new ApiError(xhr.status, "响应解析失败")); }
                };
                if (signal.aborted) xhr.abort();
                signal.addEventListener("abort", () => xhr.abort(), { once: true });
                xhr.send(fd);
            });

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
                if (s.status === "error") throw new ApiError(500, s.error || "处理失败");
            }
        } catch (e: unknown) {
            const interrupted = (e instanceof DOMException && e.name === "AbortError");
            setItems(prev => prev.map(it => it.id === item.id ? {
                ...it, status: interrupted ? "interrupted" : "error",
                error: interrupted ? undefined : (e instanceof ApiError ? e.message : "上传失败"),
                progress: "", progressPct: undefined, uploadedBytes: undefined,
            } : it));
            return false;
        }
    };

    const uploadAll = async () => {
        setRunning(true);
        abortRef.current = new AbortController();
        const { signal } = abortRef.current;
        const queue = items.filter(it => it.status === "pending" && it.file);
        let idx = 0, doneCount = 0;
        const worker = async () => {
            while (true) {
                if (signal.aborted) break;
                const i = idx++;
                if (i >= queue.length) break;
                if (await uploadOne(queue[i], signal)) doneCount++;
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
    const totalBytes    = items.filter(it => it.file).reduce((sum, it) => sum + (it.size || 0), 0);
    const uploadedBytes = items.reduce((sum, it) => {
        if (it.status === "done" || it.status === "skipped") return sum + it.size;
        if (it.status === "uploading" && typeof it.uploadedBytes === "number") return sum + it.uploadedBytes;
        return sum;
    }, 0);
    const overallPct = totalBytes > 0 ? Math.min(100, Math.round((uploadedBytes / totalBytes) * 100)) : 0;
    const overallEta = (() => {
        const uploading = items.filter(it => it.status === "uploading" && it.uploadedBytes);
        if (!uploading.length) return null;
        const speeds = uploading.map(it => {
            const elapsed = Math.max(1, (Date.now() - (startTimeRef.current[it.id] || Date.now())) / 1000);
            return (it.uploadedBytes ?? 0) / elapsed;
        }).filter(s => s > 0);
        if (!speeds.length) return null;
        const speed = speeds.reduce((a, b) => a + b, 0);
        return speed > 0 ? Math.round(Math.max(0, totalBytes - uploadedBytes) / speed) : null;
    })();

    return {
        items, dragging, setDragging, stats, running, showErrors, setShowErrors,
        detailItem, setDetailItem, addFiles, removeItem, clearDone, clearAll, retryItem,
        retryFailed, uploadAll, abort, counts, totalBytes, uploadedBytes, overallPct, overallEta,
    };
}
