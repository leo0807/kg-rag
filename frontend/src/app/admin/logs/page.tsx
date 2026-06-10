"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";

const LEVELS = ["INFO", "WARNING", "ERROR", "CRITICAL"] as const;
type Level = (typeof LEVELS)[number];

const LEVEL_COLORS: Record<Level, string> = {
  INFO:     "text-gray-400",
  WARNING:  "text-yellow-400",
  ERROR:    "text-red-400",
  CRITICAL: "text-red-300 font-semibold",
};

function lineColor(line: string): string {
  if (/CRITICAL/.test(line)) return LEVEL_COLORS.CRITICAL;
  if (/ERROR/.test(line))    return LEVEL_COLORS.ERROR;
  if (/WARNING/.test(line))  return LEVEL_COLORS.WARNING;
  return LEVEL_COLORS.INFO;
}

export default function LogsPage() {
  const [lines, setLines]   = useState<string[]>([]);
  const [level, setLevel]   = useState<Level>("INFO");
  const [search, setSearch] = useState("");
  const [file, setFile]     = useState<"backend" | "errors">("backend");
  const [loading, setLoading] = useState(false);
  const [total, setTotal]   = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const timerRef  = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ level, file, lines: "300" });
      if (search) params.set("search", search);
      const data = await fetchApi<{ lines: string[]; total: number }>(
        `/api/admin/logs?${params}`
      );
      setLines(data.lines);
      setTotal(data.total);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch { /* ignore */ } finally {
      setLoading(false);
    }
  }, [level, file, search]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh every 10s
  useEffect(() => {
    timerRef.current = setInterval(load, 10_000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [load]);

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <h1 className="text-base font-semibold text-gray-100">系统日志</h1>
        <span className="text-xs text-gray-600 ml-auto">共 {total} 行 · 每10秒自动刷新</span>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <select value={file} onChange={(e) => setFile(e.target.value as "backend" | "errors")}
          className="bg-gray-900 border border-gray-700 text-xs text-gray-300 rounded px-2 py-1">
          <option value="backend">backend.log</option>
          <option value="errors">errors.log</option>
        </select>

        <div className="flex gap-1">
          {LEVELS.map((l) => (
            <button key={l} onClick={() => setLevel(l)}
              className={`text-xs px-2 py-1 rounded border transition-colors ${
                level === l
                  ? "bg-indigo-600 border-indigo-500 text-white"
                  : "bg-gray-900 border-gray-700 text-gray-400 hover:text-gray-200"
              }`}>
              {l}
            </button>
          ))}
        </div>

        <input value={search} onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索关键词…"
          className="bg-gray-900 border border-gray-700 text-xs text-gray-300 rounded px-2 py-1 w-40" />

        <button onClick={load} disabled={loading}
          className="ml-auto text-xs px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded border border-gray-700 transition-colors disabled:opacity-50">
          {loading ? "加载中…" : "刷新"}
        </button>
      </div>

      {/* Log output */}
      <div className="bg-gray-950 border border-gray-800 rounded-xl p-3 h-[70vh] overflow-y-auto font-mono">
        {lines.length === 0 ? (
          <p className="text-xs text-gray-600 text-center py-12">暂无日志</p>
        ) : (
          lines.map((line, i) => (
            <div key={i} className={`text-[11px] leading-5 whitespace-pre-wrap break-all ${lineColor(line)}`}>
              {line}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
