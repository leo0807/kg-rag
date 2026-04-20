"use client";

import { useState, useEffect, useRef } from "react";
import {
    RefreshCw, Loader2, CheckCircle2, XCircle, AlertCircle,
    Square, RotateCcw, Trash2, Search, CheckSquare,
    FolderSync, Play, Pause, StopCircle,
} from "lucide-react";

const PIPELINES = [
    { key: "reparse",     label: "重新解析章节", desc: "修复 0 章节文档（重新提取章节结构）" },
    { key: "entities",    label: "实体提取",     desc: "Tool / Material / Process 节点" },
    { key: "constraints", label: "约束参数",     desc: "LLM 提取力矩/公差/温度" },
    { key: "tables",      label: "表格提取",     desc: "PP-Structure → Constraint 节点" },
    { key: "drawings",    label: "工程图纸",     desc: "VLM 分析尺寸标注与装配关系" },
    { key: "defects",     label: "缺陷检测",     desc: "YOLOv11 视觉质检" },
] as const;
type PK = typeof PIPELINES[number]["key"];

interface Doc { doc_id: string; title: string | null; section_count: number; }
interface Batch {
    status: string;
    total?: number; done?: number;
    current_doc?: string; current_step?: string; message?: string;
    pipelines?: string[];
    errors?: { doc_id: string; error: string }[];
    completed_docs?: string[];
    started_at?: number; finished_at?: number;
}

// ── localStorage helpers（SSR 安全） ──────────────────────────────────────────
const LS_PIPELINES = "reparse:global_options";
function lsGet(key: string): string | null {
    if (typeof window === "undefined") return null;
    try { return localStorage.getItem(key); } catch { return null; }
}
function lsSet(key: string, value: string) {
    try { localStorage.setItem(key, value); } catch {}
}
function lsRemove(key: string) {
    try { localStorage.removeItem(key); } catch {}
}
function lsKeys(): string[] {
    if (typeof window === "undefined") return [];
    try { return Object.keys(localStorage); } catch { return []; }
}

// ── 辅助函数 ──────────────────────────────────────────────────────────────────
function fmtRemaining(secs: number): string {
    if (secs <= 0) return "";
    if (secs < 60) return "约 1 分钟";
    const mins = Math.round(secs / 60);
    if (mins < 60) return `约 ${mins} 分钟`;
    const hrs = Math.floor(mins / 60);
    const rem = mins % 60;
    return rem > 0 ? `约 ${hrs} 小时 ${rem} 分钟` : `约 ${hrs} 小时`;
}

interface BackfillStatus {
    status: "idle" | "running" | "paused" | "completed";
    total: number;
    done: number;
    current_doc: string;
    percent: number;
    elapsed_seconds: number;
    estimated_remaining_seconds: number;
}

// ── 图片补全控制卡片 ──────────────────────────────────────────────────────────
function BackfillCard({ isAdmin, token }: { isAdmin: boolean; token: string }) {
    const [bf,          setBf]          = useState<BackfillStatus | null>(null);
    const [bfBusy,      setBfBusy]      = useState(false);
    const [stopConfirm, setStopConfirm] = useState(false);
    const bfPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const h = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

    async function fetchBf() {
        try {
            const r = await fetch("/api/documents/backfill/status", { headers: h });
            if (r.ok) setBf(await r.json());
        } catch {}
    }

    // 初始加载一次；running/paused 时每 3 秒轮询
    useEffect(() => {
        fetchBf();
    }, []);

    useEffect(() => {
        if (bfPollRef.current) clearInterval(bfPollRef.current);
        if (bf?.status === "running" || bf?.status === "paused") {
            bfPollRef.current = setInterval(fetchBf, 3000);
        }
        return () => { if (bfPollRef.current) clearInterval(bfPollRef.current); };
    }, [bf?.status]);

    async function bfStart() {
        setBfBusy(true);
        try {
            const r = await fetch("/api/documents/backfill/start", { method: "POST", headers: h });
            if (r.ok) setBf(await r.json() as BackfillStatus);
        } finally { setBfBusy(false); fetchBf(); }
    }

    async function bfTogglePause() {
        if (!bf) return;
        setBfBusy(true);
        try {
            const ep = bf.status === "running"
                ? "/api/documents/backfill/pause"
                : "/api/documents/backfill/resume";
            await fetch(ep, { method: "POST", headers: h });
        } finally { setBfBusy(false); fetchBf(); }
    }

    async function bfStop() {
        setStopConfirm(false);
        setBfBusy(true);
        try {
            await fetch("/api/documents/backfill/stop", { method: "POST", headers: h });
            setBf(s => s ? { ...s, status: "idle" } : s);
        } finally { setBfBusy(false); fetchBf(); }
    }

    const isRunning  = bf?.status === "running";
    const isPaused   = bf?.status === "paused";
    const isActive   = isRunning || isPaused;
    const isDone     = bf?.status === "completed";
    const pct        = Math.min(100, Math.max(0, bf?.percent ?? 0));

    return (
        <>
            <div className="bg-gray-950 border border-gray-800 rounded-xl p-4 mb-1">
                {/* 标题行 */}
                <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                        <FolderSync size={14} className={isRunning ? "text-indigo-400" : "text-gray-500"} />
                        <span className="text-sm font-medium text-white">图片补全任务</span>
                        {isRunning && (
                            <span className="px-1.5 py-0.5 bg-amber-900/40 text-amber-300 text-xs rounded-full font-medium">
                                运行中
                            </span>
                        )}
                        {isPaused && (
                            <span className="px-1.5 py-0.5 bg-gray-700 text-gray-300 text-xs rounded-full font-medium">
                                已暂停
                            </span>
                        )}
                        {isDone && (
                            <span className="px-1.5 py-0.5 bg-emerald-900/40 text-emerald-300 text-xs rounded-full font-medium">
                                已完成
                            </span>
                        )}
                    </div>

                    {/* 管理员操作按钮 */}
                    {isAdmin && (
                        <div className="flex items-center gap-2">
                            {!isActive && !isDone && (
                                <button onClick={bfStart} disabled={bfBusy}
                                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                                               bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors">
                                    {bfBusy ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
                                    启动任务
                                </button>
                            )}
                            {isActive && (
                                <>
                                    <button onClick={bfTogglePause} disabled={bfBusy}
                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                                                   border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500
                                                   disabled:opacity-50 transition-colors">
                                        {bfBusy ? <Loader2 size={11} className="animate-spin" /> :
                                            isRunning ? <Pause size={11} /> : <Play size={11} />}
                                        {isRunning ? "暂停" : "恢复"}
                                    </button>
                                    <button onClick={() => setStopConfirm(true)} disabled={bfBusy}
                                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                                                   border border-red-700/60 text-red-400 hover:bg-red-900/20
                                                   disabled:opacity-50 transition-colors">
                                        <StopCircle size={11} />停止
                                    </button>
                                </>
                            )}
                            {isDone && (
                                <button onClick={() => { setBf(s => s ? { ...s, status: "idle" } : s); }}
                                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                                               border border-gray-700 text-gray-500 hover:text-gray-300
                                               transition-colors">
                                    <Trash2 size={11} />清除
                                </button>
                            )}
                        </div>
                    )}
                </div>

                {/* 说明文字（idle 时） */}
                {!isActive && !isDone && (
                    <p className="text-xs text-gray-500 mb-2">
                        将所有未建立图像节点的文档逐份提取图片并上传至知识图谱
                    </p>
                )}

                {/* 进度条（运行中或暂停时） */}
                {isActive && (
                    <div className="mt-2 space-y-2">
                        <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                            {isRunning && pct === 0 ? (
                                <div className="h-full w-full bg-indigo-500/40 animate-pulse rounded-full" />
                            ) : (
                                <div className={`h-full rounded-full transition-all duration-500 ${isRunning ? "bg-indigo-500" : "bg-gray-600"}`}
                                    style={{ width: `${pct}%`, minWidth: pct > 0 ? "4px" : "0" }} />
                            )}
                        </div>
                        <div className="flex items-center justify-between text-xs text-gray-500">
                            <span>
                                {bf?.current_doc && (
                                    <span className="font-mono text-indigo-400 mr-2">{bf.current_doc}</span>
                                )}
                                已处理&nbsp;
                                <span className={isRunning ? "text-indigo-300" : "text-gray-300"}>
                                    {bf?.done ?? 0}
                                </span>
                                &nbsp;/&nbsp;{bf?.total ?? "—"} 份文档
                                <span className="ml-1.5 text-gray-600">({pct.toFixed(1)}%)</span>
                            </span>
                            {(bf?.estimated_remaining_seconds ?? 0) > 0 && isRunning && (
                                <span>预计剩余：{fmtRemaining(bf!.estimated_remaining_seconds)}</span>
                            )}
                        </div>
                    </div>
                )}

                {/* 完成状态 */}
                {isDone && (
                    <div className="flex items-center gap-2 text-sm text-emerald-400 mt-1">
                        <CheckCircle2 size={14} />
                        全部 {bf?.total} 份文档图片已补全
                    </div>
                )}

                {/* idle + 非管理员：无任务在运行 */}
                {!isAdmin && !isActive && !isDone && (
                    <p className="text-xs text-gray-600 mt-1">当前无图片补全任务在运行</p>
                )}
            </div>

            {/* 停止确认弹窗 */}
            {stopConfirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
                    onClick={() => setStopConfirm(false)}>
                    <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 w-96 shadow-2xl"
                        onClick={e => e.stopPropagation()}>
                        <h2 className="text-base font-semibold text-white mb-2">确认停止图片补全任务？</h2>
                        <p className="text-sm text-gray-400 mb-5">
                            下次需要手动重新启动。已处理的图片数据不会丢失，
                            下次启动时只会处理仍未补全的文档。
                        </p>
                        <div className="flex gap-3">
                            <button onClick={() => setStopConfirm(false)}
                                className="flex-1 py-2 rounded-lg border border-gray-700 text-sm text-gray-400
                                           hover:text-white transition-colors">
                                取消
                            </button>
                            <button onClick={bfStop}
                                className="flex-1 py-2 rounded-lg bg-red-700 text-white text-sm font-medium
                                           hover:bg-red-600 transition-colors">
                                确认停止
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

export function LibraryReprocessTab({ isAdmin = true }: { isAdmin?: boolean }) {
    // ── 管道选择（从 localStorage 恢复，默认四项）──────────────────────────────
    const [sel, setSel] = useState<Set<PK>>(() => {
        const stored = lsGet(LS_PIPELINES);
        if (stored) {
            try {
                const arr = JSON.parse(stored) as PK[];
                const valid = arr.filter(k => PIPELINES.some(p => p.key === k));
                if (valid.length > 0) return new Set(valid);
            } catch {}
        }
        return new Set<PK>(["entities", "constraints", "tables", "drawings"]);
    });

    // ── 文档列表 & 选择（从 localStorage reparse:doc:* 恢复）──────────────────
    const [docs,      setDocs]      = useState<Doc[]>([]);
    const [docsLoading, setDocsLoading] = useState(true);
    const [docSearch, setDocSearch] = useState("");
    const [selectedDocs, setSelectedDocs] = useState<Set<string>>(() => {
        const ids = lsKeys()
            .filter(k => k.startsWith("reparse:doc:"))
            .map(k => k.replace("reparse:doc:", ""));
        return new Set(ids);
    });

    // ── 批量任务状态 ────────────────────────────────────────────────────────────
    // 从 sessionStorage 读取上次状态，避免切换 Tab 时进度消失
    const [batch,  setBatch]  = useState<Batch>(() => {
        try {
            const stored = sessionStorage.getItem("kg_batch_status");
            return stored ? (JSON.parse(stored) as Batch) : { status: "idle" };
        } catch { return { status: "idle" }; }
    });
    const [busy,   setBusy]   = useState(false);
    const [confirm, setConfirm] = useState(false);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
    const h = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

    /** 更新 batch 状态，同步写入 sessionStorage */
    function updateBatch(next: Batch | ((prev: Batch) => Batch)) {
        setBatch(prev => {
            const val = typeof next === "function" ? next(prev) : next;
            try { sessionStorage.setItem("kg_batch_status", JSON.stringify(val)); } catch {}
            return val;
        });
    }

    // ── 加载全量文档列表（逐页拉取，无数量上限）─────────────────────────────────
    async function fetchDocs() {
        setDocsLoading(true);
        try {
            const PER = 500;
            const first = await fetch(`/api/documents?per_page=${PER}&page=1`, { headers: h }).then(r => r.json());
            let all: Doc[] = first.data ?? [];
            const pages: number = first.pages ?? 1;
            if (pages > 1) {
                const rest = await Promise.all(
                    Array.from({ length: pages - 1 }, (_, i) =>
                        fetch(`/api/documents?per_page=${PER}&page=${i + 2}`, { headers: h }).then(r => r.json())
                    )
                );
                for (const d of rest) all = all.concat(d.data ?? []);
            }
            setDocs(all);
        } finally {
            setDocsLoading(false);
        }
    }

    useEffect(() => { fetchDocs(); }, []);

    // ── 管道选择变化时写 localStorage ─────────────────────────────────────────
    useEffect(() => {
        lsSet(LS_PIPELINES, JSON.stringify([...sel]));
    }, [sel]);

    // ── 文档勾选变化时同步 localStorage（全量覆盖）───────────────────────────
    useEffect(() => {
        // 先清除所有旧的 doc 选择记录，再写入当前集合
        lsKeys()
            .filter(k => k.startsWith("reparse:doc:"))
            .forEach(lsRemove);
        selectedDocs.forEach(id => lsSet(`reparse:doc:${id}`, "1"));
    }, [selectedDocs]);

    // ── 初始化拉取批量状态（以服务端为准，修正 sessionStorage 的过期状态）────
    useEffect(() => {
        fetch("/api/documents/reprocess-all/status", { headers: h })
            .then(r => r.json()).then(updateBatch).catch(() => {});
    }, []);

    // ── 批量完成后刷新文档列表，更新章节数目 ─────────────────────────────────
    useEffect(() => {
        if (batch.status === "completed") fetchDocs();
    }, [batch.status]);

    // ── 轮询 ──────────────────────────────────────────────────────────────────
    useEffect(() => {
        if (batch.status === "running") {
            pollRef.current = setInterval(async () => {
                const r = await fetch("/api/documents/reprocess-all/status", { headers: h });
                const d: Batch = await r.json();
                updateBatch(d);
                if (d.status !== "running") clearInterval(pollRef.current!);
            }, 3000);
        }
        return () => { if (pollRef.current) clearInterval(pollRef.current); };
    }, [batch.status]);

    // ── 文档过滤 ──────────────────────────────────────────────────────────────
    const filteredDocs = docs.filter(d =>
        !docSearch ||
        d.doc_id.toLowerCase().includes(docSearch.toLowerCase()) ||
        (d.title ?? "").toLowerCase().includes(docSearch.toLowerCase())
    );
    const allSelected  = filteredDocs.length > 0 && filteredDocs.every(d => selectedDocs.has(d.doc_id));
    const someSelected = selectedDocs.size > 0;

    function toggleDoc(id: string) {
        setSelectedDocs(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
    }
    function toggleAll() {
        if (allSelected) {
            setSelectedDocs(prev => { const n = new Set(prev); filteredDocs.forEach(d => n.delete(d.doc_id)); return n; });
        } else {
            setSelectedDocs(prev => { const n = new Set(prev); filteredDocs.forEach(d => n.add(d.doc_id)); return n; });
        }
    }
    function clearSelection() { setSelectedDocs(new Set()); }

    // ── 操作 ──────────────────────────────────────────────────────────────────
    async function start() {
        setConfirm(false); setBusy(true);
        // 乐观更新：立即显示进度面板，无需等待后端响应
        const estimatedTotal = someSelected ? selectedDocs.size : docs.length;
        updateBatch({ status: "running", total: estimatedTotal, done: 0, pipelines: [...sel] });
        try {
            const body: Record<string, unknown> = { pipelines: [...sel] };
            if (someSelected) body.doc_ids = [...selectedDocs];
            const r = await fetch("/api/documents/reprocess-all", {
                method: "POST", headers: h, body: JSON.stringify(body),
            });
            const d = await r.json();
            if (d.status === "started" || d.status === "running") {
                // 用服务端精确数量覆盖估算值
                updateBatch(prev => ({ ...prev, total: d.total }));
                // 提交成功后清除文档勾选记录（任务已入队，无需再保留）
                lsKeys()
                    .filter(k => k.startsWith("reparse:doc:"))
                    .forEach(lsRemove);
                setSelectedDocs(new Set());
            } else {
                // 后端拒绝（如 no_documents 等），回退到 idle
                updateBatch({ status: "idle" });
            }
        } catch {
            // 网络错误，回退到 idle
            updateBatch({ status: "idle" });
        } finally { setBusy(false); }
    }

    async function cancel() {
        await fetch("/api/documents/reprocess-all/cancel", { method: "POST", headers: h });
        updateBatch(b => ({ ...b, status: "cancelling" }));
    }

    async function resume() {
        setBusy(true);
        try {
            const body: Record<string, unknown> = { pipelines: [...sel] };
            if (someSelected) body.doc_ids = [...selectedDocs];
            const r = await fetch("/api/documents/reprocess-all/resume", {
                method: "POST", headers: h, body: JSON.stringify(body),
            });
            const d = await r.json();
            if (d.status === "resumed") updateBatch(b => ({ ...b, status: "running" }));
        } finally { setBusy(false); }
    }

    async function clearBatch() {
        await fetch("/api/documents/reprocess-all/clear", { method: "POST", headers: h });
        updateBatch({ status: "idle" });
    }

    const isRunning  = batch.status === "running";
    const isDone     = ["completed", "cancelled", "failed", "interrupted"].includes(batch.status);
    const canResume  = isDone && (batch.completed_docs?.length ?? 0) < (batch.total ?? 0) && batch.status !== "completed";
    const progress   = batch.total ? Math.round(((batch.done ?? 0) / batch.total) * 100) : 0;
    // 当前文档在各管道中的进度：用 current_step 和 pipelines 推算
    const activePipelines = batch.pipelines ?? [];
    const stepIdx  = activePipelines.indexOf(batch.current_step ?? "");
    const docPct   = activePipelines.length > 0 && stepIdx >= 0
        ? Math.round((stepIdx / activePipelines.length) * 100)
        : 0;

    // ── 渲染 ──────────────────────────────────────────────────────────────────
    return (
        <div className="space-y-5 w-full">
            {/* ── 图片补全控制卡片（管理员全控制 / 普通用户仅进度） ── */}
            <BackfillCard isAdmin={isAdmin} token={token} />

            <div className="grid grid-cols-1 xl:grid-cols-[1.6fr_1fr] gap-5">

                {/* ── 左列：文档选择 + 管道选择 ── */}
                <div className="space-y-4">

                    {/* 文档选择面板 */}
                    <div className="bg-gray-950 border border-gray-800 rounded-xl p-4">
                        <div className="flex items-center justify-between mb-3">
                            <span className="text-xs text-gray-500 uppercase tracking-wider">
                                选择待处理文档
                                {someSelected
                                    ? <span className="ml-2 text-indigo-400 normal-case">已选 {selectedDocs.size} 个</span>
                                    : <span className="ml-2 text-gray-600 normal-case">（未选则处理全部 {docs.length} 个）</span>
                                }
                            </span>
                            <button onClick={clearSelection} disabled={!someSelected}
                                className="text-xs text-gray-500 hover:text-gray-300 disabled:opacity-30 transition-colors">
                                清除选择
                            </button>
                        </div>

                        {/* 搜索框 */}
                        <div className="relative mb-2">
                            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                            <input value={docSearch} onChange={e => setDocSearch(e.target.value)}
                                placeholder="搜索规范编号或标题..."
                                className="w-full pl-7 pr-3 py-1.5 bg-gray-900 border border-gray-700 rounded text-xs
                                           text-gray-200 outline-none focus:border-indigo-500 placeholder-gray-600" />
                        </div>

                        {/* 全选行 */}
                        <div className="flex items-center gap-2 px-2 py-1.5 border-b border-gray-800 mb-1">
                            <button onClick={toggleAll} className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-200 transition-colors">
                                {allSelected
                                    ? <CheckSquare size={13} className="text-indigo-400" />
                                    : <Square size={13} />}
                                {allSelected ? "取消全选" : "全选当前"}
                                {filteredDocs.length !== docs.length && (
                                    <span className="text-gray-600">({filteredDocs.length} 个)</span>
                                )}
                            </button>
                        </div>

                        {/* 文档列表 */}
                        <div className="max-h-56 overflow-y-auto space-y-0.5 pr-1">
                            {docsLoading ? (
                                <div className="flex items-center gap-2 py-4 justify-center text-xs text-gray-500">
                                    <Loader2 size={12} className="animate-spin" />加载中...
                                </div>
                            ) : filteredDocs.length === 0 ? (
                                <div className="py-4 text-center text-xs text-gray-600">无匹配文档</div>
                            ) : filteredDocs.map(doc => (
                                <label key={doc.doc_id}
                                    className={`flex items-center gap-2.5 px-2 py-1.5 rounded cursor-pointer transition-colors
                                        ${selectedDocs.has(doc.doc_id)
                                            ? "bg-indigo-900/20 border border-indigo-800/40"
                                            : "hover:bg-gray-900 border border-transparent"}
                                        ${isRunning ? "pointer-events-none opacity-50" : ""}`}>
                                    <input type="checkbox" className="accent-indigo-500 shrink-0"
                                        checked={selectedDocs.has(doc.doc_id)}
                                        disabled={isRunning}
                                        onChange={() => toggleDoc(doc.doc_id)} />
                                    <span className="font-mono text-xs text-indigo-400 shrink-0 w-20">{doc.doc_id}</span>
                                    <span className="text-xs text-gray-300 flex-1 truncate">{doc.title ?? "—"}</span>
                                    <span className={`text-xs shrink-0 tabular-nums ${doc.section_count === 0 ? "text-red-500" : "text-gray-600"}`}>
                                        {doc.section_count}章
                                    </span>
                                </label>
                            ))}
                        </div>
                    </div>

                    {/* 管道选择 */}
                    <div className="bg-gray-950 border border-gray-800 rounded-xl p-4">
                        <div className="text-xs text-gray-500 uppercase tracking-wider mb-3">处理管道</div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4">
                            {PIPELINES.map(({ key, label, desc }) => (
                                <label key={key}
                                    className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                                        sel.has(key) ? "border-indigo-600/60 bg-indigo-900/20" : "border-gray-800 hover:border-gray-700"
                                    } ${isRunning ? "opacity-50 pointer-events-none" : ""}`}>
                                    <input type="checkbox" className="mt-0.5 accent-indigo-500"
                                        checked={sel.has(key)} disabled={isRunning}
                                        onChange={() => setSel(prev => {
                                            const n = new Set(prev);
                                            n.has(key) ? n.delete(key) : n.add(key);
                                            return n;
                                        })} />
                                    <div>
                                        <div className="text-sm text-gray-200 font-medium">{label}</div>
                                        <div className="text-xs text-gray-500">{desc}</div>
                                    </div>
                                </label>
                            ))}
                        </div>

                        {/* 操作按钮 */}
                        <div className="flex gap-2 flex-wrap">
                            <button onClick={() => setConfirm(true)}
                                disabled={isRunning || busy || sel.size === 0}
                                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium
                                           bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                                {busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                                {someSelected ? `批量处理 (${selectedDocs.size} 个)` : "批量处理全部文档"}
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
                            {isDone && (
                                <button onClick={clearBatch}
                                    className="px-4 py-2.5 rounded-lg text-sm font-medium border border-gray-700 text-gray-400
                                               hover:bg-gray-800 transition-colors flex items-center gap-1.5">
                                    <Trash2 size={13} />清除
                                </button>
                            )}
                        </div>
                    </div>
                </div>

                {/* ── 右列：进度面板 ── */}
                {batch.status !== "idle" ? (
                    <div className="bg-gray-950 border border-gray-800 rounded-xl p-5 space-y-3">
                        <div className="flex items-center justify-between">
                            <span className="text-sm font-medium text-white">批量任务</span>
                            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                                isRunning                         ? "bg-amber-900/40 text-amber-300" :
                                batch.status === "completed"       ? "bg-emerald-900/40 text-emerald-300" :
                                batch.status === "cancelled"       ? "bg-gray-700 text-gray-300" :
                                batch.status === "cancelling"      ? "bg-orange-900/40 text-orange-300" :
                                batch.status === "interrupted"     ? "bg-yellow-900/40 text-yellow-300" :
                                "bg-red-900/40 text-red-300"}`}>
                                {batch.status === "running"    ? "运行中" :
                                 batch.status === "completed"  ? "已完成" :
                                 batch.status === "cancelled"  ? "已中止" :
                                 batch.status === "cancelling" ? "中止中" :
                                 batch.status === "interrupted"? "已中断(服务重启)" : "失败"}
                            </span>
                        </div>

                        {/* 总进度条 */}
                        {(isRunning || isDone) && (
                            <>
                                <div>
                                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                                        <span>文档总进度</span>
                                        <span className="tabular-nums">{batch.done ?? 0} / {batch.total ?? "—"} 个文档&nbsp;({progress}%)</span>
                                    </div>
                                    <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                                        {isRunning && progress === 0 ? (
                                            /* 尚未完成首个文档时显示脉冲动画（不确定进度） */
                                            <div className="h-full w-full bg-indigo-500/50 animate-pulse rounded-full" />
                                        ) : (
                                            <div className="h-full bg-indigo-500 transition-all duration-700 rounded-full"
                                                style={{ width: `${progress}%`, minWidth: progress > 0 ? "6px" : "0" }} />
                                        )}
                                    </div>
                                </div>

                                {/* 当前文档进度条 */}
                                {isRunning && batch.current_doc && activePipelines.length > 0 && (
                                    <div>
                                        <div className="flex justify-between text-xs text-gray-500 mb-1">
                                            <span className="font-mono text-indigo-400 truncate max-w-[60%]">{batch.current_doc}</span>
                                            <span className="tabular-nums">{batch.current_step || "—"}&nbsp;({stepIdx >= 0 ? stepIdx : 0}/{activePipelines.length})</span>
                                        </div>
                                        <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                                            <div className="h-full bg-indigo-400/60 transition-all duration-500 rounded-full"
                                                style={{ width: `${docPct}%` }} />
                                        </div>
                                    </div>
                                )}
                            </>
                        )}

                        {isRunning && batch.message && (
                            <div className="flex items-center gap-1.5 text-xs text-gray-500 pt-0.5">
                                <Loader2 size={10} className="animate-spin shrink-0" />
                                <span className="italic truncate">{batch.message}</span>
                            </div>
                        )}

                        {/* 后台运行提示 */}
                        {isRunning && (
                            <div className="text-[10px] text-gray-600 border-t border-gray-800 pt-2 leading-relaxed">
                                任务在服务端后台运行，关闭浏览器或退出登录后仍会继续处理。重新登录后可在此查看进度。
                            </div>
                        )}

                        {batch.status === "completed" && (
                            <div className="flex items-center gap-2 text-sm text-emerald-400">
                                <CheckCircle2 size={15} />全部 {batch.total} 个文档处理完成
                            </div>
                        )}
                        {batch.status === "cancelled" && (
                            <div className="text-xs text-gray-400">
                                已完成 {batch.completed_docs?.length ?? 0} / {batch.total} 个，点击"续跑"从断点继续
                            </div>
                        )}

                        {(batch.errors?.length ?? 0) > 0 && (
                            <div className="space-y-1 pt-1 border-t border-gray-800">
                                <div className="flex items-center gap-1.5 text-xs text-red-400 mb-1">
                                    <AlertCircle size={11} />{batch.errors!.length} 个文档失败
                                </div>
                                {batch.errors!.slice(0, 8).map((e, i) => (
                                    <div key={i} className="flex items-start gap-2 text-xs">
                                        <XCircle size={11} className="text-red-500 mt-0.5 shrink-0" />
                                        <span className="font-mono text-gray-400 shrink-0">{e.doc_id}</span>
                                        <span className="text-gray-600 truncate">{e.error}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ) : (
                    <div className="bg-gray-950 border border-gray-800 rounded-xl p-5">
                        <div className="text-sm font-medium text-white mb-2">任务进度</div>
                        <div className="text-xs text-gray-500 leading-relaxed">
                            从左侧选择需要处理的文档（不选则处理全部），勾选管道后点击"批量处理"启动任务。
                            运行期间可在此查看实时进度和错误详情，完成后点击"清除"重置状态。
                        </div>
                    </div>
                )}
            </div>

            {/* 确认弹窗 */}
            {confirm && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
                    onClick={() => setConfirm(false)}>
                    <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 w-96 shadow-2xl"
                        onClick={e => e.stopPropagation()}>
                        <h2 className="text-base font-semibold text-white mb-2">确认批量重新处理？</h2>
                        <p className="text-sm text-gray-400 mb-1">
                            {someSelected
                                ? `将对选中的 ${selectedDocs.size} 个文档依次运行：`
                                : `将对全部 ${docs.length} 个文档依次运行：`}
                        </p>
                        <ul className="text-sm text-indigo-300 mb-4 list-disc list-inside space-y-0.5">
                            {[...sel].map(k => <li key={k}>{PIPELINES.find(p => p.key === k)?.label}</li>)}
                        </ul>
                        <p className="text-xs text-gray-500 mb-5">处理前将自动拍摄快照，可随时中止。</p>
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
