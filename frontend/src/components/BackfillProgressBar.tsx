"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Loader2, Pause, Play, FolderSync } from "lucide-react";

interface BackfillStatus {
    status: "idle" | "running" | "paused" | "completed";
    total: number;
    done: number;
    current_doc: string;
    percent: number;
    elapsed_seconds: number;
    estimated_remaining_seconds: number;
}

function fmtRemaining(secs: number): string {
    if (secs <= 0) return "";
    if (secs < 60)  return "约 1 分钟";
    const mins = Math.round(secs / 60);
    if (mins < 60)  return `约 ${mins} 分钟`;
    const hrs  = Math.floor(mins / 60);
    const rem  = mins % 60;
    return rem > 0 ? `约 ${hrs} 小时 ${rem} 分钟` : `约 ${hrs} 小时`;
}

function getToken(): string {
    if (typeof window === "undefined") return "";
    return localStorage.getItem("token") ?? "";
}

function authHeaders(): Record<string, string> {
    const t = getToken();
    return t ? { Authorization: `Bearer ${t}` } : {};
}

export default function BackfillProgressBar() {
    const [status,  setStatus]  = useState<BackfillStatus | null>(null);
    const [loading, setLoading] = useState(false);   // 暂停/恢复按钮 loading
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchStatus = useCallback(async () => {
        try {
            const res = await fetch("/api/documents/backfill/status", {
                headers: authHeaders(),
            });
            if (!res.ok) return;
            const data: BackfillStatus = await res.json();
            setStatus(data);
        } catch {
            // 静默失败，不影响主页面
        }
    }, []);

    // 轮询：每 3 秒拉一次
    useEffect(() => {
        fetchStatus();
        timerRef.current = setInterval(fetchStatus, 3000);
        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
        };
    }, [fetchStatus]);

    // idle / completed → 不渲染任何内容
    if (!status || status.status === "idle" || status.status === "completed") {
        return null;
    }

    const isRunning = status.status === "running";
    const isPaused  = status.status === "paused";

    async function handleToggle() {
        if (loading) return;
        setLoading(true);
        try {
            const endpoint = isRunning
                ? "/api/documents/backfill/pause"
                : "/api/documents/backfill/resume";
            await fetch(endpoint, {
                method:  "POST",
                headers: authHeaders(),
            });
            // 立即刷新状态
            await fetchStatus();
        } catch {
            // 静默失败
        } finally {
            setLoading(false);
        }
    }

    const barColor = isRunning ? "bg-indigo-500" : "bg-gray-500";
    const pct      = Math.min(100, Math.max(0, status.percent));

    return (
        <div className={`
            mb-4 rounded-lg border px-4 py-3
            ${isRunning
                ? "bg-indigo-950/40 border-indigo-500/30"
                : "bg-gray-900/60 border-gray-700/50"}
        `}>
            {/* 顶行：图标 + 标题 + 暂停标签 + 按钮 */}
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <FolderSync
                        className={`w-4 h-4 ${isRunning ? "text-indigo-400" : "text-gray-500"}`}
                    />
                    <span className={`text-sm font-medium ${isRunning ? "text-indigo-200" : "text-gray-400"}`}>
                        图片补全任务
                    </span>
                    {isPaused && (
                        <span className="px-1.5 py-0.5 bg-gray-700 text-gray-400 text-xs rounded">
                            已暂停
                        </span>
                    )}
                    {isRunning && status.current_doc && (
                        <span className="text-xs text-gray-500 font-mono">
                            {status.current_doc}
                        </span>
                    )}
                </div>

                <button
                    onClick={handleToggle}
                    disabled={loading}
                    className={`
                        flex items-center gap-1.5 px-3 py-1 rounded text-xs font-medium
                        transition-colors disabled:opacity-50
                        ${isRunning
                            ? "bg-gray-700 text-gray-300 hover:bg-gray-600"
                            : "bg-indigo-700 text-indigo-100 hover:bg-indigo-600"}
                    `}
                >
                    {loading ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                    ) : isRunning ? (
                        <Pause className="w-3 h-3" />
                    ) : (
                        <Play className="w-3 h-3" />
                    )}
                    {isRunning ? "暂停" : "恢复"}
                </button>
            </div>

            {/* 进度条 */}
            <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden mb-2">
                <div
                    className={`h-full rounded-full transition-all duration-500 ${barColor}`}
                    style={{ width: `${pct}%` }}
                />
            </div>

            {/* 底行：进度数字 + 预计时间 */}
            <div className="flex items-center justify-between text-xs text-gray-500">
                <span>
                    已处理&nbsp;
                    <span className={isRunning ? "text-indigo-300" : "text-gray-300"}>
                        {status.done}
                    </span>
                    &nbsp;/&nbsp;共&nbsp;{status.total}&nbsp;份文档
                    <span className="ml-2 text-gray-600">({pct.toFixed(1)}%)</span>
                </span>
                {status.estimated_remaining_seconds > 0 && isRunning && (
                    <span>{fmtRemaining(status.estimated_remaining_seconds)}</span>
                )}
            </div>
        </div>
    );
}
