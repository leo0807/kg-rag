"use client";
import { useEffect, useRef, useState } from "react";
import { LiveQueryFeed }          from "./LiveQueryFeed";
import { LiveErrorMonitor }       from "./LiveErrorMonitor";
import { LivePerformanceMetrics } from "./LivePerformanceMetrics";

type RawEvent = { event: string; ts: number; data: Record<string, unknown> };

const WS_URL = () => {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const token = localStorage.getItem("token") ?? "";
  return `${proto}//${window.location.host}/api/realtime/dashboard?token=${token}`;
};

const MAX_EVENTS = 200;

export default function RealtimePage() {
  const [events, setEvents]       = useState<RawEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [paused, setPaused]       = useState(false);
  const wsRef    = useRef<WebSocket | null>(null);
  const pauseRef = useRef(false);
  const aliveRef = useRef(true);

  useEffect(() => {
    aliveRef.current = true;

    const connect = () => {
      if (!aliveRef.current) return;
      const ws = new WebSocket(WS_URL());
      wsRef.current = ws;

      ws.onopen  = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (aliveRef.current) setTimeout(connect, 3000);
      };
      ws.onerror = () => { /* browser closes automatically on error */ };
      ws.onmessage = (e) => {
        if (pauseRef.current) return;
        try {
          const msg = JSON.parse(e.data) as RawEvent;
          if (msg.event === "heartbeat" || msg.event === "pong") return;
          setEvents(prev => [...prev.slice(-(MAX_EVENTS - 1)), msg]);
        } catch { /* ignore */ }
      };

      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 25000);

      return () => {
        clearInterval(ping);
        ws.close();
      };
    };

    const cleanup = connect();
    return () => {
      aliveRef.current = false;
      cleanup?.();
    };
  }, []);

  const togglePause = () => {
    pauseRef.current = !pauseRef.current;
    setPaused(pauseRef.current);
  };

  const clear = () => setEvents([]);

  return (
    <div className="p-6 max-w-7xl space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">实时监控仪表盘</h1>
          <p className="text-gray-400 text-sm mt-1">系统事件实时流 · WebSocket 长连接</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border ${
            connected ? "border-green-700 text-green-300 bg-green-950" : "border-red-700 text-red-300 bg-red-950"
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-red-400"}`} />
            {connected ? "已连接" : "重连中…"}
          </span>
          <button onClick={togglePause}
            className="text-xs px-3 py-1.5 rounded border border-gray-700 text-gray-400 hover:text-white">
            {paused ? "▶ 继续" : "⏸ 暂停"}
          </button>
          <button onClick={clear} className="text-xs px-3 py-1.5 rounded border border-gray-700 text-gray-400 hover:text-white">
            清空
          </button>
        </div>
      </div>

      {/* Performance metrics (top) */}
      <LivePerformanceMetrics events={events} />

      {/* Two-column: query feed + error monitor */}
      <div className="grid grid-cols-2 gap-4">
        <LiveQueryFeed events={events} />
        <LiveErrorMonitor events={events} />
      </div>

      {/* Event log */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <div className="px-4 py-3 bg-gray-800 text-white text-sm font-medium">
          所有事件 ({events.length}/{MAX_EVENTS})
        </div>
        <div className="overflow-y-auto max-h-48 text-xs font-mono p-3 space-y-1">
          {events.slice().reverse().slice(0, 50).map((e, i) => (
            <div key={i} className="flex gap-3 text-gray-400">
              <span className="text-gray-600">{new Date(e.ts * 1000).toLocaleTimeString("zh-CN")}</span>
              <span className="text-blue-400">{e.event}</span>
              <span className="truncate">{JSON.stringify(e.data)}</span>
            </div>
          ))}
          {events.length === 0 && <div className="text-gray-600">等待事件…</div>}
        </div>
      </div>
    </div>
  );
}
