"use client";

import { AlertTriangle, Loader2, RefreshCw, ScanSearch } from "lucide-react";
import { useConflicts } from "./useConflicts";
import { ConflictList } from "./ConflictList";

export default function ConflictsPage() {
    const {
        scan, scanning, conflicts, total, stats, error,
        filterStatus, setFilterStatus, filterSeverity, setFilterSeverity,
        filterType, setFilterType, expanded, updating,
        startScan, loadConflicts, loadStats, changeStatus, toggleExpand, arbitrate,
    } = useConflicts();

    return (
        <div className="flex-1 overflow-auto bg-gray-950 p-6 space-y-6">
            {/* Header */}
            <div className="rounded-3xl border border-gray-800 bg-[radial-gradient(circle_at_top_left,rgba(239,68,68,0.15),transparent_40%),radial-gradient(circle_at_top_right,rgba(234,179,8,0.1),transparent_38%),#111827] p-6">
                <div className="max-w-3xl">
                    <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                        <AlertTriangle size={22} className="text-amber-400" />
                        规范冲突检测
                    </h1>
                    <p className="mt-2 text-sm leading-6 text-gray-400">
                        自动扫描跨文档的约束矛盾（数值冲突）与语义矛盾（LLM 判断），帮助识别知识库中的规范不一致问题。
                    </p>
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                    <button type="button" onClick={startScan}
                        disabled={scanning || scan?.status === "running"}
                        className="inline-flex items-center gap-2 px-4 h-10 rounded-xl bg-amber-500 text-gray-950 font-medium hover:bg-amber-400 disabled:opacity-50 transition-colors">
                        {scanning ? <Loader2 size={15} className="animate-spin" /> : <ScanSearch size={15} />}
                        开始扫描
                    </button>
                    <button type="button" onClick={() => { loadConflicts(); loadStats(); }}
                        className="inline-flex items-center gap-2 px-4 h-10 rounded-xl border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 transition-colors">
                        <RefreshCw size={14} />刷新
                    </button>
                    {stats && (
                        <div className="flex items-center gap-4 ml-4 text-sm text-gray-400">
                            <span>共 <b className="text-white">{stats.total}</b> 条冲突</span>
                            {stats.by_status["pending"] > 0 && <span className="text-amber-400">{stats.by_status["pending"]} 待审核</span>}
                            {stats.by_severity["high"] > 0 && <span className="text-rose-400">{stats.by_severity["high"]} 高危</span>}
                        </div>
                    )}
                </div>
            </div>

            {/* Scan progress */}
            {scan && (
                <div className="rounded-3xl border border-gray-800 bg-gray-900 p-5">
                    <div className="flex items-center gap-2 text-white font-medium mb-3">
                        <ScanSearch size={15} />
                        扫描任务
                        <span className={`ml-2 text-xs px-2 py-0.5 rounded-full ${
                            scan.status === "completed" ? "bg-emerald-500/20 text-emerald-400"
                            : scan.status === "failed" ? "bg-rose-500/20 text-rose-400"
                            : scan.status === "running" ? "bg-blue-500/20 text-blue-400"
                            : "bg-gray-700 text-gray-400"
                        }`}>{scan.status}</span>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        {[
                            ["约束冲突", scan.constraint_count],
                            ["语义冲突", scan.semantic_count],
                            ["实体对", `${scan.entity_pairs_done} / ${scan.entity_pairs_total}`],
                            ["总计入库", scan.total_conflicts],
                        ].map(([label, value]) => (
                            <div key={label as string} className="rounded-xl bg-gray-950 border border-gray-800 p-3">
                                <div className="text-gray-500 text-xs">{label}</div>
                                <div className="text-white text-lg font-semibold">{value}</div>
                            </div>
                        ))}
                    </div>
                    {scan.status === "running" && scan.phase && (
                        <div className="mt-3 text-xs text-gray-400">
                            阶段：{scan.phase === "constraint" ? "约束规则检测" : "LLM 语义分析中…"}
                        </div>
                    )}
                    {scan.error && <div className="mt-3 text-xs text-rose-400">{scan.error}</div>}
                </div>
            )}

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-3 text-sm">
                <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
                    className="h-9 rounded-lg bg-gray-900 border border-gray-800 px-3 text-gray-300">
                    <option value="">全部状态</option>
                    <option value="pending">待审核</option>
                    <option value="confirmed">已确认</option>
                    <option value="dismissed">已忽略</option>
                    <option value="resolved">已解决</option>
                </select>
                <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)}
                    className="h-9 rounded-lg bg-gray-900 border border-gray-800 px-3 text-gray-300">
                    <option value="">全部严重度</option>
                    <option value="high">高危</option>
                    <option value="medium">中等</option>
                    <option value="low">低风险</option>
                </select>
                <select value={filterType} onChange={e => setFilterType(e.target.value)}
                    className="h-9 rounded-lg bg-gray-900 border border-gray-800 px-3 text-gray-300">
                    <option value="">全部类型</option>
                    <option value="constraint">约束冲突</option>
                    <option value="semantic">语义冲突</option>
                </select>
                <span className="text-gray-500">共 {total} 条</span>
            </div>

            {error && (
                <div className="px-4 py-3 rounded-xl bg-red-950/40 border border-red-800/40 text-sm text-red-300">{error}</div>
            )}

            <ConflictList
                conflicts={conflicts} expanded={expanded} updating={updating}
                onToggle={toggleExpand} onChangeStatus={changeStatus} onArbitrate={arbitrate}
            />
        </div>
    );
}
