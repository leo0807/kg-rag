"use client";

import { useState, useEffect, useRef } from "react";
import { RefreshCw, Loader2, CheckCircle2, XCircle, AlertCircle, Database } from "lucide-react";

const PIPELINES = [
    { key: "entities",    label: "实体提取",   desc: "工具 / 材料 / 工序节点" },
    { key: "constraints", label: "约束参数",   desc: "LLM 文本约束提取" },
    { key: "tables",      label: "表格提取",   desc: "PP-Structure → Constraint" },
    { key: "drawings",    label: "工程图纸",   desc: "VLM 图纸专项分析" },
    { key: "defects",     label: "缺陷检测",   desc: "YOLOv11 视觉质检" },
] as const;
type PipelineKey = typeof PIPELINES[number]["key"];

interface BatchStatus {
    status:       "idle" | "running" | "completed" | "failed";
    total?:       number;
    done?:        number;
    current_doc?: string;
    pipelines?:   string[];
    errors?:      { doc_id: string; error: string }[];
    started_at?:  number;
    finished_at?: number;
}

export default function AdminReprocessPage() {
    const [selected,  setSelected]  = useState<Set<PipelineKey>>(new Set(["entities", "constraints", "tables", "drawings"]));
    const [batch,     setBatch]     = useState<BatchStatus>({ status: "idle" });
    const [starting,  setStarting]  = useState(false);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const token = typeof window !== "undefined" ? (localStorage.getItem("token") ?? "") : "";
    const headers = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

    useEffect(() => {
        fetch("/api/documents/reprocess-all/status", { headers })
            .then(r => r.json()).then(setBatch).catch(() => {});
    }, []);

    useEffect(() => {
        if (batch.status === "running") {
            pollRef.current = setInterval(async () => {
                const r = await fetch("/api/documents/reprocess-all/status", { headers });
                const data: BatchStatus = await r.json();
                setBatch(data);
                if (data.status !== "running") clearInterval(pollRef.current!);
            }, 3000);
        }
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [batch.status]);

    function toggle(key: PipelineKey) {
        setSelected(prev => {
            const next = new Set(prev);
            next.has(key) ? next.delete(key) : next.add(key);
            return next;
        });
    }

    async function startBatch() {
        if (selected.size === 0 || batch.status === "running") return;
        setStarting(true);
        try {
            const r = await fetch("/api/documents/reprocess-all", {
                method: "POST",
                headers,
                body: JSON.stringify({ pipelines: [...selected] }),
            });
            const data = await r.json();
            if (data.status === "started") {
                setBatch({ status: "running", total: data.total, done: 0, pipelines: [...selected] });
            }
        } finally {
            setStarting(false);
        }
    }

    const isRunning  = batch.status === "running";
    const progress   = batch.total ? Math.round(((batch.done ?? 0) / batch.total) * 100) : 0;

    return (
        <div className="p-8 max-w-3xl mx-auto">
            <div className="flex items-center gap-3 mb-8">
                <Database size={22} className="text-indigo-400" />
                <div>
                    <h1 className="text-xl font-semibold text-white">文档重新处理</h1>
                    <p className="text-sm text-gray-500 mt-0.5">对已入库文档运行新数据处理管道，补充图谱节点</p>
                </div>
            </div>

            {/* 管道选择 */}
            <div className="bg-gray-950 border border-gray-800 rounded-xl p-5 mb-5">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">处理管道</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {PIPELINES.map(({ key, label, desc }) => (
                        <label
                            key={key}
                            className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                                selected.has(key)
                                    ? "border-indigo-600/60 bg-indigo-900/20"
                                    : "border-gray-800 hover:border-gray-700"
                            } ${isRunning ? "opacity-50 cursor-not-allowed" : ""}`}
                        >
                            <input
                                type="checkbox"
                                className="mt-0.5 accent-indigo-500"
                                checked={selected.has(key)}
                                onChange={() => toggle(key)}
                                disabled={isRunning}
                            />
                            <div>
                                <div className="text-sm text-gray-200 font-medium">{label}</div>
                                <div className="text-xs text-gray-500">{desc}</div>
                            </div>
                        </label>
                    ))}
                </div>

                <button
                    onClick={startBatch}
                    disabled={isRunning || starting || selected.size === 0}
                    className="mt-4 w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium
                               bg-indigo-600 text-white hover:bg-indigo-500 transition-colors
                               disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isRunning || starting
                        ? <><Loader2 size={14} className="animate-spin" />处理中...</>
                        : <><RefreshCw size={14} />批量重新处理全部文档</>
                    }
                </button>
            </div>

            {/* 进度卡片 */}
            {batch.status !== "idle" && (
                <div className="bg-gray-950 border border-gray-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center justify-between">
                        <div className="text-sm font-medium text-white">批量任务状态</div>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            isRunning         ? "bg-amber-900/40 text-amber-300" :
                            batch.status === "completed" ? "bg-emerald-900/40 text-emerald-300" :
                            "bg-red-900/40 text-red-300"
                        }`}>
                            {isRunning ? "运行中" : batch.status === "completed" ? "已完成" : "失败"}
                        </span>
                    </div>

                    {/* 进度条 */}
                    {isRunning && (
                        <>
                            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-indigo-500 transition-all duration-500"
                                    style={{ width: `${progress}%` }}
                                />
                            </div>
                            <div className="flex items-center justify-between text-xs text-gray-400">
                                <span>{batch.done ?? 0} / {batch.total ?? "?"} 个文档</span>
                                <span>{progress}%</span>
                            </div>
                            {batch.current_doc && (
                                <div className="flex items-center gap-1.5 text-xs text-gray-500">
                                    <Loader2 size={10} className="animate-spin" />
                                    正在处理：<span className="font-mono text-indigo-400">{batch.current_doc}</span>
                                </div>
                            )}
                        </>
                    )}

                    {/* 完成摘要 */}
                    {batch.status === "completed" && (
                        <div className="flex items-center gap-2 text-sm text-emerald-400">
                            <CheckCircle2 size={16} />
                            <span>全部 {batch.total} 个文档处理完成</span>
                        </div>
                    )}

                    {/* 错误列表 */}
                    {(batch.errors?.length ?? 0) > 0 && (
                        <div className="space-y-1">
                            <div className="flex items-center gap-1.5 text-xs text-red-400 mb-2">
                                <AlertCircle size={12} />
                                {batch.errors!.length} 个文档处理失败
                            </div>
                            {batch.errors!.map((e, i) => (
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
        </div>
    );
}
