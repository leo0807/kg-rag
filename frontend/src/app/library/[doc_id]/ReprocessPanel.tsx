"use client";

import { useState, useEffect, useRef } from "react";
import {
    RefreshCw, CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp,
    Square, RotateCcw, Clock, ShieldCheck, AlertTriangle, Info, CheckCircle2,
} from "lucide-react";

const PIPELINES = [
    { key: "reparse",     label: "重新解析章节", desc: "重新从 PDF 提取章节结构（修复 0 章节文档）" },
    { key: "images",      label: "图片补全",     desc: "重新提取图片节点并写入图谱" },
    { key: "entities",    label: "实体提取",     desc: "工具 / 材料 / 工序节点" },
    { key: "constraints", label: "约束参数",     desc: "LLM 提取力矩/公差/温度约束" },
    { key: "tables",      label: "表格提取",     desc: "PP-Structure → Constraint 节点" },
    { key: "drawings",    label: "工程图纸",     desc: "VLM 重新分析尺寸标注与装配关系" },
    { key: "defects",     label: "缺陷检测",     desc: "YOLOv11 视觉质检" },
] as const;
type PK = typeof PIPELINES[number]["key"];

interface Snapshot { snapshot_id: string; timestamp: number; constraints_count: number; defects_count: number; images_count: number; }
interface TaskStatus { status: string; pipelines?: string[]; current?: string; message?: string; results?: Record<string, number>; error?: string; snapshot_id?: string; }

interface ValidationIssue { level: "error" | "warning" | "info"; code: string; detail: string; }
interface ValidationReport {
    doc_id: string; valid: boolean; score: number;
    issues: ValidationIssue[];
    stats: { section_count: number; empty_sections: number; avg_content_len: number; title: string; };
}
interface Props { docId: string; onComplete?: () => void; }

function fmtTime(ts: number) {
    return new Date(ts * 1000).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function ReprocessPanel({ docId, onComplete }: Props) {
    const [selected,   setSelected]   = useState<Set<PK>>(new Set<PK>(["images","entities","constraints","tables","drawings"]));
    const [task,       setTask]       = useState<TaskStatus>({ status: "idle" });
    const [snapshots,  setSnapshots]  = useState<Snapshot[]>([]);
    const [busy,       setBusy]       = useState(false);
    const [confirm,    setConfirm]    = useState(false);
    const [showRes,    setShowRes]    = useState(false);
    const [rollTarget, setRollTarget] = useState("");
    const [rolling,    setRolling]    = useState(false);
    const [validating, setValidating] = useState(false);
    const [valReport,  setValReport]  = useState<ValidationReport | null>(null);
    const [showVal,    setShowVal]    = useState(false);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    const h = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

    function loadSnapshots() {
        fetch(`/api/documents/${docId}/snapshots`, { headers: h })
            .then(r => r.json()).then(d => setSnapshots(d.snapshots ?? [])).catch(() => {});
    }

    useEffect(() => {
        fetch(`/api/documents/${docId}/reprocess/status`, { headers: h })
            .then(r => r.json()).then(setTask).catch(() => {});
        loadSnapshots();
    }, [docId]);

    useEffect(() => {
        const active = task.status === "running" || task.status === "pending";
        if (active) {
            pollRef.current = setInterval(async () => {
                const r = await fetch(`/api/documents/${docId}/reprocess/status`, { headers: h });
                const d: TaskStatus = await r.json();
                setTask(d);
                if (d.status !== "running" && d.status !== "pending") {
                    clearInterval(pollRef.current!);
                    setShowRes(true);
                    loadSnapshots();
                    if (d.status === "completed") onComplete?.();
                }
            }, 2000);
        }
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [task.status]);

    async function start() {
        setConfirm(false); setBusy(true);
        try {
            const r = await fetch(`/api/documents/${docId}/reprocess`, {
                method: "POST", headers: h, body: JSON.stringify({ pipelines: [...selected] }),
            });
            const d = await r.json();
            setTask({ status: d.status === "started" ? "pending" : d.status, pipelines: [...selected] });
            setShowRes(false);
        } finally { setBusy(false); }
    }

    async function cancel() {
        await fetch(`/api/documents/${docId}/reprocess/cancel`, { method: "POST", headers: h });
    }

    async function runValidation() {
        setValidating(true); setValReport(null); setShowVal(true);
        try {
            const r = await fetch(`/api/documents/${docId}/validate`, { headers: h });
            if (r.ok) setValReport(await r.json());
        } finally { setValidating(false); }
    }

    async function rollback() {
        if (!rollTarget) return;
        setRolling(true);
        try {
            const r = await fetch(`/api/documents/${docId}/rollback/${rollTarget}`, { method: "POST", headers: h });
            if (r.ok) { setRollTarget(""); loadSnapshots(); }
        } finally { setRolling(false); }
    }

    const isRunning = task.status === "running" || task.status === "pending";
    const isDone    = ["completed","cancelled","failed"].includes(task.status);

    return (
        <div className="space-y-4">
            {/* 管道选择 */}
            <div className="space-y-2">
                <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">选择处理管道</div>
                {PIPELINES.map(({ key, label, desc }) => (
                    <label key={key}
                        className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                            selected.has(key) ? "border-indigo-600/60 bg-indigo-900/20" : "border-gray-800 hover:border-gray-700"
                        } ${isRunning ? "opacity-50 pointer-events-none" : ""}`}>
                        <input type="checkbox" className="mt-0.5 accent-indigo-500"
                            checked={selected.has(key)} disabled={isRunning}
                            onChange={() => setSelected(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n; })} />
                        <div><div className="text-sm text-gray-200 font-medium">{label}</div>
                            <div className="text-xs text-gray-500">{desc}</div></div>
                    </label>
                ))}
            </div>

            {/* 操作按钮 */}
            <div className="flex gap-2">
                <button onClick={() => setConfirm(true)} disabled={isRunning || busy || selected.size === 0}
                    className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium
                               bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                    {isRunning ? <><Loader2 size={13} className="animate-spin" />处理中...</> : <><RefreshCw size={13} />重新处理</>}
                </button>
                {isRunning && (
                    <button onClick={cancel}
                        className="px-3 py-2 rounded-lg text-sm border border-red-700 text-red-400 hover:bg-red-900/20 transition-colors flex items-center gap-1.5">
                        <Square size={12} />中止
                    </button>
                )}
            </div>

            {/* 进度 */}
            {isRunning && (
                <div className="px-3 py-2.5 bg-gray-900 border border-gray-800 rounded-lg text-xs">
                    <div className="flex items-center gap-2 text-amber-400 mb-1">
                        <Loader2 size={11} className="animate-spin" />
                        <span className="font-medium">{task.current || "初始化"}</span>
                    </div>
                    <div className="text-gray-500">{task.message}</div>
                </div>
            )}

            {/* 结果 */}
            {isDone && task.results && (
                <div className={`border rounded-lg overflow-hidden ${task.status === "completed" ? "border-emerald-800/50" : "border-gray-700"}`}>
                    <button onClick={() => setShowRes(v => !v)}
                        className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium">
                        <span className="flex items-center gap-1.5">
                            {task.status === "completed" ? <CheckCircle size={12} className="text-emerald-400" /> : <XCircle size={12} className="text-gray-400" />}
                            {task.status === "completed" ? "处理完成" : task.status === "cancelled" ? "已中止" : "处理失败"}
                        </span>
                        {showRes ? <ChevronUp size={12} className="text-gray-500" /> : <ChevronDown size={12} className="text-gray-500" />}
                    </button>
                    {showRes && (
                        <div className="px-3 pb-3 space-y-1">
                            {task.error && <div className="text-xs text-red-400 mb-2">{task.error}</div>}
                            {Object.entries(task.results).map(([pipe, count]) => (
                                <div key={pipe} className="flex justify-between text-xs">
                                    <span className="text-gray-400">{PIPELINES.find(p => p.key === pipe)?.label ?? pipe}</span>
                                    <span className={`font-mono ${count < 0 ? "text-red-400" : "text-emerald-400"}`}>
                                        {count < 0 ? "失败" : `+${count}`}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* 解析质量验证 */}
            <div className="border border-gray-800 rounded-lg overflow-hidden">
                <button onClick={() => showVal ? setShowVal(false) : runValidation()}
                    className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-medium text-gray-300 hover:text-white hover:bg-gray-900 transition-colors">
                    <span className="flex items-center gap-1.5">
                        <ShieldCheck size={13} className="text-indigo-400" />
                        验证解析质量
                        {valReport && (
                            <span className={`ml-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                valReport.valid ? "bg-emerald-900/40 text-emerald-300" : "bg-red-900/40 text-red-300"
                            }`}>
                                {valReport.valid ? "通过" : "有问题"} · {valReport.score}分
                            </span>
                        )}
                    </span>
                    {validating ? <Loader2 size={11} className="animate-spin text-gray-500" /> :
                        showVal ? <ChevronUp size={11} className="text-gray-500" /> : <ChevronDown size={11} className="text-gray-500" />}
                </button>

                {showVal && (
                    <div className="px-3 pb-3 pt-1 border-t border-gray-800 space-y-2">
                        {validating && (
                            <div className="flex items-center gap-2 text-xs text-gray-500 py-2">
                                <Loader2 size={11} className="animate-spin" />验证中...
                            </div>
                        )}
                        {valReport && !validating && (
                            <>
                                {/* 摘要统计 */}
                                <div className="grid grid-cols-3 gap-2 text-center py-1">
                                    {[
                                        { label: "章节数", value: valReport.stats.section_count },
                                        { label: "空章节", value: valReport.stats.empty_sections },
                                        { label: "平均字数", value: valReport.stats.avg_content_len },
                                    ].map(({ label, value }) => (
                                        <div key={label} className="bg-gray-900 rounded px-2 py-1.5">
                                            <div className="text-sm font-mono font-medium text-gray-200">{value}</div>
                                            <div className="text-[10px] text-gray-500">{label}</div>
                                        </div>
                                    ))}
                                </div>

                                {/* 问题列表 */}
                                {valReport.issues.length === 0 ? (
                                    <div className="flex items-center gap-1.5 text-xs text-emerald-400 py-1">
                                        <CheckCircle2 size={12} />无问题，解析质量良好
                                    </div>
                                ) : (
                                    <div className="space-y-1">
                                        {valReport.issues.map((issue, i) => (
                                            <div key={i} className="flex items-start gap-2 text-xs">
                                                {issue.level === "error"   && <XCircle      size={11} className="text-red-400 mt-0.5 shrink-0" />}
                                                {issue.level === "warning" && <AlertTriangle size={11} className="text-amber-400 mt-0.5 shrink-0" />}
                                                {issue.level === "info"    && <Info          size={11} className="text-blue-400 mt-0.5 shrink-0" />}
                                                <span className="text-gray-400 leading-snug">{issue.detail}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                )}
            </div>

            {/* 快照 & 回滚 */}
            {snapshots.length > 0 && (
                <div className="border border-gray-800 rounded-lg p-3 space-y-2">
                    <div className="text-xs text-gray-500 uppercase tracking-wider">回滚到历史快照</div>
                    <select value={rollTarget} onChange={e => setRollTarget(e.target.value)}
                        className="w-full px-2.5 py-1.5 bg-gray-900 border border-gray-700 rounded text-xs text-gray-200 outline-none focus:border-indigo-500">
                        <option value="">— 选择快照 —</option>
                        {snapshots.map(s => (
                            <option key={s.snapshot_id} value={s.snapshot_id}>
                                {fmtTime(s.timestamp)} · 约束 {s.constraints_count} · 图纸 {s.images_count} · 缺陷 {s.defects_count}
                            </option>
                        ))}
                    </select>
                    <button onClick={rollback} disabled={!rollTarget || rolling || isRunning}
                        className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium
                                   border border-amber-700 text-amber-400 hover:bg-amber-900/20
                                   disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                        {rolling ? <Loader2 size={11} className="animate-spin" /> : <RotateCcw size={11} />}
                        执行回滚
                    </button>
                </div>
            )}

            {/* 确认弹窗 */}
            {confirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
                    onClick={() => setConfirm(false)}>
                    <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 w-80 shadow-2xl"
                        onClick={e => e.stopPropagation()}>
                        <h2 className="text-sm font-semibold text-white mb-2">确认重新处理？</h2>
                        <p className="text-xs text-gray-400 mb-3">将运行以下管道：</p>
                        <ul className="text-xs text-indigo-300 mb-3 list-disc list-inside space-y-0.5">
                            {[...selected].map(k => <li key={k}>{PIPELINES.find(p => p.key === k)?.label}</li>)}
                        </ul>
                        <p className="text-xs text-gray-500 mb-4 flex items-center gap-1"><Clock size={11} />处理前将自动拍摄快照，可随时回滚</p>
                        <div className="flex gap-2">
                            <button onClick={() => setConfirm(false)}
                                className="flex-1 py-1.5 rounded-lg border border-gray-700 text-xs text-gray-400 hover:text-white transition-colors">取消</button>
                            <button onClick={start}
                                className="flex-1 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500 transition-colors">确认</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
