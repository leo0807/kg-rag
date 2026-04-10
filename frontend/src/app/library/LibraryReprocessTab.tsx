"use client";

import { useState, useEffect, useRef } from "react";
import { RefreshCw, Loader2, CheckCircle2, XCircle, AlertCircle, Square, RotateCcw } from "lucide-react";

const PIPELINES = [
    { key: "entities",    label: "实体提取",   desc: "Tool / Material / Process 节点" },
    { key: "constraints", label: "约束参数",   desc: "LLM 提取力矩/公差/温度" },
    { key: "tables",      label: "表格提取",   desc: "PP-Structure → Constraint 节点" },
    { key: "drawings",    label: "工程图纸",   desc: "VLM 分析尺寸标注与装配关系" },
    { key: "defects",     label: "缺陷检测",   desc: "YOLOv11 视觉质检" },
] as const;
type PK = typeof PIPELINES[number]["key"];

interface Batch {
    status:         string;
    total?:         number;
    done?:          number;
    current_doc?:   string;
    pipelines?:     string[];
    errors?:        { doc_id: string; error: string }[];
    completed_docs?: string[];
    started_at?:    number;
    finished_at?:   number;
}

export function LibraryReprocessTab() {
    const [sel,      setSel]      = useState<Set<PK>>(new Set(["entities","constraints","tables","drawings"]));
    const [batch,    setBatch]    = useState<Batch>({ status: "idle" });
    const [busy,     setBusy]     = useState(false);
    const [confirm,  setConfirm]  = useState(false);   // confirm modal
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    const h = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

    useEffect(() => {
        fetch("/api/documents/reprocess-all/status", { headers: h })
            .then(r => r.json()).then(setBatch).catch(() => {});
    }, []);

    useEffect(() => {
        if (batch.status === "running") {
            pollRef.current = setInterval(async () => {
                const r = await fetch("/api/documents/reprocess-all/status", { headers: h });
                const d: Batch = await r.json();
                setBatch(d);
                if (d.status !== "running") clearInterval(pollRef.current!);
            }, 3000);
        }
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [batch.status]);

    async function start() {
        setConfirm(false); setBusy(true);
        try {
            const r = await fetch("/api/documents/reprocess-all", {
                method: "POST", headers: h,
                body: JSON.stringify({ pipelines: [...sel] }),
            });
            const d = await r.json();
            if (d.status === "started") setBatch({ status: "running", total: d.total, done: 0, pipelines: [...sel] });
        } finally { setBusy(false); }
    }

    async function cancel() {
        await fetch("/api/documents/reprocess-all/cancel", { method: "POST", headers: h });
        setBatch(b => ({ ...b, status: "cancelling" }));
    }

    async function resume() {
        setBusy(true);
        try {
            const r = await fetch("/api/documents/reprocess-all/resume", {
                method: "POST", headers: h,
                body: JSON.stringify({ pipelines: [...sel] }),
            });
            const d = await r.json();
            if (d.status === "resumed") setBatch(b => ({ ...b, status: "running" }));
        } finally { setBusy(false); }
    }

    const isRunning  = batch.status === "running";
    const isDone     = ["completed","cancelled","failed"].includes(batch.status);
    const canResume  = isDone && (batch.completed_docs?.length ?? 0) < (batch.total ?? 0) && batch.status !== "completed";
    const progress   = batch.total ? Math.round(((batch.done ?? 0) / batch.total) * 100) : 0;

    return (
        <div className="space-y-5 max-w-2xl">
            {/* 管道选择 */}
            <div className="bg-gray-950 border border-gray-800 rounded-xl p-5">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">处理管道</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
                    {PIPELINES.map(({ key, label, desc }) => (
                        <label key={key}
                            className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                                sel.has(key) ? "border-indigo-600/60 bg-indigo-900/20" : "border-gray-800 hover:border-gray-700"
                            } ${isRunning ? "opacity-50 pointer-events-none" : ""}`}>
                            <input type="checkbox" className="mt-0.5 accent-indigo-500"
                                checked={sel.has(key)} disabled={isRunning}
                                onChange={() => setSel(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n; })} />
                            <div><div className="text-sm text-gray-200 font-medium">{label}</div>
                                <div className="text-xs text-gray-500">{desc}</div></div>
                        </label>
                    ))}
                </div>

                <div className="flex gap-2">
                    <button onClick={() => setConfirm(true)} disabled={isRunning || busy || sel.size === 0}
                        className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium
                                   bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                        {busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                        批量重新处理全部文档
                    </button>
                    {canResume && (
                        <button onClick={resume} disabled={busy}
                            className="px-4 py-2.5 rounded-lg text-sm font-medium border border-indigo-600 text-indigo-300
                                       hover:bg-indigo-900/30 disabled:opacity-50 transition-colors flex items-center gap-1.5">
                            <RotateCcw size={13} />续跑
                        </button>
                    )}
                    {isRunning && (
                        <button onClick={cancel}
                            className="px-4 py-2.5 rounded-lg text-sm font-medium border border-red-700 text-red-400
                                       hover:bg-red-900/20 transition-colors flex items-center gap-1.5">
                            <Square size={13} />中止
                        </button>
                    )}
                </div>
            </div>

            {/* 进度 */}
            {batch.status !== "idle" && (
                <div className="bg-gray-950 border border-gray-800 rounded-xl p-5 space-y-3">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-white">批量任务</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            isRunning ? "bg-amber-900/40 text-amber-300" :
                            batch.status === "completed" ? "bg-emerald-900/40 text-emerald-300" :
                            batch.status === "cancelled" ? "bg-gray-700 text-gray-300" :
                            "bg-red-900/40 text-red-300"}`}>
                            {isRunning ? "运行中" : batch.status === "completed" ? "已完成" :
                             batch.status === "cancelled" ? "已中止" : "失败"}
                        </span>
                    </div>
                    {(isRunning || isDone) && (
                        <>
                            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                <div className="h-full bg-indigo-500 transition-all duration-500"
                                    style={{ width: `${progress}%` }} />
                            </div>
                            <div className="flex justify-between text-xs text-gray-400">
                                <span>{batch.done ?? 0} / {batch.total ?? "?"} 个文档</span>
                                <span>{progress}%</span>
                            </div>
                        </>
                    )}
                    {isRunning && batch.current_doc && (
                        <div className="flex items-center gap-1.5 text-xs text-gray-500">
                            <Loader2 size={10} className="animate-spin" />
                            <span className="font-mono text-indigo-400">{batch.current_doc}</span>
                        </div>
                    )}
                    {batch.status === "completed" && (
                        <div className="flex items-center gap-2 text-sm text-emerald-400">
                            <CheckCircle2 size={15} />全部 {batch.total} 个文档处理完成
                        </div>
                    )}
                    {batch.status === "cancelled" && (
                        <div className="text-xs text-gray-400">
                            已完成 {batch.completed_docs?.length ?? 0} / {batch.total} 个文档，点击"续跑"从断点继续
                        </div>
                    )}
                    {(batch.errors?.length ?? 0) > 0 && (
                        <div className="space-y-1 pt-1 border-t border-gray-800">
                            <div className="flex items-center gap-1.5 text-xs text-red-400 mb-1">
                                <AlertCircle size={11} />{batch.errors!.length} 个文档失败
                            </div>
                            {batch.errors!.slice(0, 5).map((e, i) => (
                                <div key={i} className="flex items-start gap-2 text-xs">
                                    <XCircle size={11} className="text-red-500 mt-0.5 shrink-0" />
                                    <span className="font-mono text-gray-400">{e.doc_id}</span>
                                    <span className="text-gray-600 truncate">{e.error}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* 确认弹窗 */}
            {confirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
                    onClick={() => setConfirm(false)}>
                    <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 w-96 shadow-2xl"
                        onClick={e => e.stopPropagation()}>
                        <h2 className="text-base font-semibold text-white mb-2">确认批量重新处理？</h2>
                        <p className="text-sm text-gray-400 mb-1">将对所有已入库文档依次运行以下管道：</p>
                        <ul className="text-sm text-indigo-300 mb-4 list-disc list-inside space-y-0.5">
                            {[...sel].map(k => <li key={k}>{PIPELINES.find(p => p.key === k)?.label}</li>)}
                        </ul>
                        <p className="text-xs text-gray-500 mb-5">处理前将自动拍摄快照，可随时中止并回滚。</p>
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
