"use client";

import { useState, useEffect, useRef } from "react";
import { RefreshCw, CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp } from "lucide-react";

const PIPELINES = [
    { key: "entities",    label: "实体提取",   desc: "工具 / 材料 / 工序节点重新提取" },
    { key: "constraints", label: "约束参数",   desc: "LLM 提取文本中的力矩/公差/温度约束" },
    { key: "tables",      label: "表格提取",   desc: "PP-Structure 解析规范表格 → Constraint 节点" },
    { key: "drawings",    label: "工程图纸",   desc: "VLM 重新分析图片中的尺寸标注与装配关系" },
    { key: "defects",     label: "缺陷检测",   desc: "YOLOv11 对工件图片进行质量缺陷检测" },
] as const;

type PipelineKey = typeof PIPELINES[number]["key"];

interface TaskStatus {
    status:      "idle" | "pending" | "running" | "completed" | "failed";
    pipelines?:  string[];
    current?:    string;
    message?:    string;
    results?:    Record<string, number>;
    error?:      string;
    started_at?: number;
    finished_at?: number;
}

interface Props {
    docId: string;
}

export function ReprocessPanel({ docId }: Props) {
    const [selected,    setSelected]    = useState<Set<PipelineKey>>(new Set(["entities", "constraints", "tables", "drawings"]));
    const [task,        setTask]        = useState<TaskStatus>({ status: "idle" });
    const [submitting,  setSubmitting]  = useState(false);
    const [showResults, setShowResults] = useState(false);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const token   = typeof window !== "undefined" ? (localStorage.getItem("token") ?? "") : "";

    // 页面加载时拉取上次任务状态
    useEffect(() => {
        fetch(`/api/documents/${docId}/reprocess/status`, {
            headers: { Authorization: `Bearer ${token}` },
        }).then(r => r.json()).then(setTask).catch(() => {});
    }, [docId]);

    // 运行中时轮询
    useEffect(() => {
        if (task.status === "running" || task.status === "pending") {
            pollRef.current = setInterval(async () => {
                const r = await fetch(`/api/documents/${docId}/reprocess/status`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                const data: TaskStatus = await r.json();
                setTask(data);
                if (data.status !== "running" && data.status !== "pending") {
                    clearInterval(pollRef.current!);
                    setShowResults(true);
                }
            }, 2000);
        }
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [task.status]);

    function toggle(key: PipelineKey) {
        setSelected(prev => {
            const next = new Set(prev);
            next.has(key) ? next.delete(key) : next.add(key);
            return next;
        });
    }

    async function startReprocess() {
        if (selected.size === 0) return;
        setSubmitting(true);
        try {
            const r = await fetch(`/api/documents/${docId}/reprocess`, {
                method: "POST",
                headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                body: JSON.stringify({ pipelines: [...selected] }),
            });
            const data = await r.json();
            setTask({ status: data.status === "started" ? "pending" : data.status, pipelines: [...selected] });
            setShowResults(false);
        } finally {
            setSubmitting(false);
        }
    }

    const isRunning  = task.status === "running" || task.status === "pending";
    const isDone     = task.status === "completed" || task.status === "failed";

    return (
        <div className="space-y-4">
            {/* 管道选择 */}
            <div className="space-y-2">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">选择处理管道</div>
                {PIPELINES.map(({ key, label, desc }) => (
                    <label
                        key={key}
                        className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                            selected.has(key)
                                ? "border-indigo-600/60 bg-indigo-900/20"
                                : "border-gray-800 hover:border-gray-700"
                        }`}
                    >
                        <input
                            type="checkbox"
                            className="mt-0.5 accent-indigo-500"
                            checked={selected.has(key)}
                            onChange={() => toggle(key)}
                            disabled={isRunning}
                        />
                        <div className="min-w-0">
                            <div className="text-sm text-gray-200 font-medium">{label}</div>
                            <div className="text-xs text-gray-500 mt-0.5">{desc}</div>
                        </div>
                    </label>
                ))}
            </div>

            {/* 启动按钮 */}
            <button
                onClick={startReprocess}
                disabled={isRunning || submitting || selected.size === 0}
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium
                           bg-indigo-600 text-white hover:bg-indigo-500 transition-colors
                           disabled:opacity-50 disabled:cursor-not-allowed"
            >
                {isRunning
                    ? <><Loader2 size={14} className="animate-spin" />处理中...</>
                    : <><RefreshCw size={14} />开始重新处理</>
                }
            </button>

            {/* 进度 */}
            {isRunning && (
                <div className="px-3 py-2.5 bg-gray-900 border border-gray-800 rounded-lg">
                    <div className="flex items-center gap-2 text-xs text-amber-400 mb-1">
                        <Loader2 size={11} className="animate-spin" />
                        <span className="font-medium">{task.current || "初始化"}</span>
                    </div>
                    <div className="text-xs text-gray-500">{task.message}</div>
                </div>
            )}

            {/* 结果 */}
            {isDone && task.results && (
                <div className={`border rounded-lg overflow-hidden ${task.status === "completed" ? "border-emerald-800/50" : "border-red-800/50"}`}>
                    <button
                        onClick={() => setShowResults(v => !v)}
                        className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium"
                    >
                        <span className="flex items-center gap-1.5">
                            {task.status === "completed"
                                ? <CheckCircle size={12} className="text-emerald-400" />
                                : <XCircle size={12} className="text-red-400" />
                            }
                            {task.status === "completed" ? "处理完成" : "处理失败"}
                        </span>
                        {showResults ? <ChevronUp size={12} className="text-gray-500" /> : <ChevronDown size={12} className="text-gray-500" />}
                    </button>
                    {showResults && (
                        <div className="px-3 pb-3 space-y-1">
                            {task.error && (
                                <div className="text-xs text-red-400 mb-2">{task.error}</div>
                            )}
                            {Object.entries(task.results).map(([pipe, count]) => {
                                const info = PIPELINES.find(p => p.key === pipe);
                                return (
                                    <div key={pipe} className="flex items-center justify-between text-xs">
                                        <span className="text-gray-400">{info?.label ?? pipe}</span>
                                        <span className={`font-mono ${count < 0 ? "text-red-400" : "text-emerald-400"}`}>
                                            {count < 0 ? "失败" : `+${count}`}
                                        </span>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
