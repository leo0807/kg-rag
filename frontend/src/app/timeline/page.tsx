"use client";

import { useState, useEffect } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, Brush, ReferenceLine,
} from "recharts";
import { fetchApi } from "@/lib/api";
import { Calendar, GitCompare, BookOpen } from "lucide-react";
import { TimelineCompare } from "./TimelineCompare";

interface DailyEntry {
  date: string; docs_added: number; sections_added: number;
  images_added: number; tables_added: number;
}
interface TimelineData {
  daily: DailyEntry[]; total_span_days: number; first_doc: string; latest_doc: string;
}
interface DocEntry { doc_id: string; title: string; version: string; section_count: number; }

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { color: string; name: string; dataKey: string; value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-xs shadow-xl">
      <div className="font-medium text-gray-200 mb-1.5">{label}</div>
      {payload.map(p => (
        <div key={p.dataKey} className="flex justify-between gap-4">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="text-white font-mono">{p.value?.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

export default function TimelinePage() {
  const [data, setData] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [dateDocs, setDateDocs] = useState<DocEntry[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [compareOpen, setCompareOpen] = useState(false);

  useEffect(() => {
    fetchApi<TimelineData>("/api/timeline")
      .then(setData)
      .catch(() => setError("加载失败"))
      .finally(() => setLoading(false));
  }, []);

  async function handleDateClick(entry: DailyEntry) {
    setSelectedDate(entry.date);
    setCompareOpen(false);
    setDocsLoading(true);
    try {
      const r = await fetchApi<{ docs: DocEntry[] }>(`/api/timeline/docs?date=${entry.date}`);
      setDateDocs(r.docs);
    } catch { setDateDocs([]); }
    finally { setDocsLoading(false); }
  }

  const daily = data?.daily ?? [];
  const firstDate = daily[0]?.date;
  const showPanel = selectedDate !== null || compareOpen;

  return (
    <div className="flex flex-col h-full bg-gray-950 text-white">
      {/* Header */}
      <div className="border-b border-gray-800 px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <Calendar size={20} className="text-indigo-400 shrink-0" />
          <div>
            <h1 className="text-lg font-bold leading-tight">知识演化时间轴</h1>
            <p className="text-xs text-gray-400 mt-0.5">每日入库统计 — 点击图表查看当日文档</p>
          </div>
        </div>
        {data && (
          <div className="flex items-center gap-5 text-xs">
            <span className="text-gray-400">首个：<span className="text-white font-mono">{data.first_doc}</span></span>
            <span className="text-gray-400">最新：<span className="text-white font-mono">{data.latest_doc}</span></span>
            <span className="text-gray-400">覆盖 <span className="text-indigo-400 font-semibold">{data.total_span_days}</span> 天</span>
            <button onClick={() => { setCompareOpen(v => !v); setSelectedDate(null); }}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                ${compareOpen ? "bg-indigo-500 text-white" : "bg-indigo-600 hover:bg-indigo-500 text-white"}`}>
              <GitCompare size={13} /> 版本对比
            </button>
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden min-h-0">
        {/* Chart */}
        <div className="flex-1 p-6 overflow-auto min-w-0">
          {loading && <p className="text-gray-400 text-sm animate-pulse text-center mt-20">加载中…</p>}
          {error  && <p className="text-red-400 text-sm text-center mt-20">{error}</p>}
          {!loading && !error && daily.length === 0 && (
            <p className="text-gray-500 text-sm text-center mt-20">暂无数据，入库文档后将自动生成时间轴</p>
          )}
          {daily.length > 0 && (
            <>
              <p className="text-xs text-gray-500 mb-3">拖动底部刷选器缩放时间范围 · 点击折线处查看当日详情</p>
              <ResponsiveContainer width="100%" height={380}>
                <AreaChart data={daily} margin={{ top: 8, right: 24, left: 0, bottom: 0 }}
                  onClick={(e: unknown) => { const ev = e as { activePayload?: { payload: DailyEntry }[] }; if (ev?.activePayload?.[0]) handleDateClick(ev.activePayload[0].payload); }}>
                  <defs>
                    {[["docs","#3b82f6"],["secs","#f97316"],["imgs","#22c55e"],["tbls","#a855f7"]].map(([id, c]) => (
                      <linearGradient key={id} id={`grad-${id}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor={c} stopOpacity={0.5} />
                        <stop offset="95%" stopColor={c} stopOpacity={0.05} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10 }} />
                  <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: "#4b5563", strokeWidth: 1 }} />
                  <Legend wrapperStyle={{ fontSize: 11, color: "#9ca3af", paddingTop: 8 }} />
                  {firstDate && (
                    <ReferenceLine x={firstDate} stroke="#6366f1" strokeDasharray="4 3"
                      label={{ value: "首次入库", fill: "#818cf8", fontSize: 9, position: "insideTopRight" }} />
                  )}
                  <Area type="monotone" dataKey="docs_added"     name="文档" stackId="a" stroke="#3b82f6" fill="url(#grad-docs)" strokeWidth={2} />
                  <Area type="monotone" dataKey="sections_added" name="章节" stackId="a" stroke="#f97316" fill="url(#grad-secs)" strokeWidth={2} />
                  <Area type="monotone" dataKey="images_added"   name="图片" stackId="a" stroke="#22c55e" fill="url(#grad-imgs)" strokeWidth={2} />
                  <Area type="monotone" dataKey="tables_added"   name="表格" stackId="a" stroke="#a855f7" fill="url(#grad-tbls)" strokeWidth={2} />
                  <Brush dataKey="date" height={22} stroke="#374151" fill="#111827" travellerWidth={6} />
                </AreaChart>
              </ResponsiveContainer>
            </>
          )}
        </div>

        {/* Side panel */}
        {showPanel && (
          <div className="w-72 border-l border-gray-800 flex flex-col overflow-hidden shrink-0">
            {compareOpen ? (
              <TimelineCompare onClose={() => setCompareOpen(false)} />
            ) : selectedDate ? (
              <>
                <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between shrink-0">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <BookOpen size={14} className="text-indigo-400" /> {selectedDate}
                  </div>
                  <button onClick={() => setSelectedDate(null)} className="text-gray-500 hover:text-white text-xs">✕</button>
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2">
                  {docsLoading && <p className="text-gray-500 text-xs animate-pulse">加载中…</p>}
                  {!docsLoading && dateDocs.length === 0 && <p className="text-gray-500 text-xs">当日无入库文档</p>}
                  {dateDocs.map(doc => (
                    <div key={doc.doc_id} className="rounded-lg border border-gray-800 bg-gray-900 px-3 py-2">
                      <div className="font-mono text-xs text-indigo-300">{doc.doc_id}</div>
                      <div className="text-xs text-gray-300 mt-0.5 line-clamp-2">{doc.title}</div>
                      <div className="text-[10px] text-gray-500 mt-1">
                        {doc.section_count} 章节{doc.version ? ` · v${doc.version}` : ""}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
