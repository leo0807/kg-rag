"use client";
import { useEffect, useRef, useState } from "react";

type QueryEvent = {
  event: string; ts: number;
  data: { user_id?: string; question?: string; latency_ms?: number };
};

export function LiveQueryFeed({ events }: { events: QueryEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  const queryEvents = events.filter(e => e.event.startsWith("query."));

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden flex flex-col" style={{ height: 340 }}>
      <div className="px-4 py-3 bg-gray-800 flex items-center justify-between">
        <h3 className="text-white text-sm font-medium">实时查询流</h3>
        <span className="text-xs text-gray-400">{queryEvents.length} 条事件</span>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        {queryEvents.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-600 text-sm">等待事件…</div>
        ) : (
          queryEvents.slice(-50).map((e, i) => (
            <div key={i} className="flex items-start gap-3 text-xs py-1.5 border-b border-gray-800">
              <span className="text-gray-500 shrink-0 font-mono">
                {new Date(e.ts * 1000).toLocaleTimeString("zh-CN")}
              </span>
              <span className={`shrink-0 px-1.5 py-0.5 rounded text-[10px] ${
                e.event === "query.completed" ? "bg-green-900 text-green-300" : "bg-blue-900 text-blue-300"
              }`}>
                {e.event === "query.completed" ? "完成" : "进行中"}
              </span>
              <span className="text-gray-300 truncate flex-1">{e.data.question ?? "—"}</span>
              {e.data.latency_ms != null && (
                <span className={`shrink-0 ${e.data.latency_ms > 3000 ? "text-red-400" : "text-gray-500"}`}>
                  {e.data.latency_ms}ms
                </span>
              )}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
