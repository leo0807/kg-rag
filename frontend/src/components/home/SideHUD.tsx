"use client";

import { useEffect, useState } from "react";

const LEFT_METRICS = [
  { label: "CPU_LOAD",  pct: 72, color: "#22d3ee" },
  { label: "MEM_USAGE", pct: 58, color: "#60a5fa" },
  { label: "GPU_UTIL",  pct: 89, color: "#818cf8" },
  { label: "NET_TX",    pct: 43, color: "#4ade80" },
  { label: "DISK_IO",   pct: 31, color: "#fb923c" },
];

const RIGHT_STATS = [
  { label: "GRAPH_NODES",  val: "42,817",  color: "#22d3ee" },
  { label: "VECTOR_INDEX", val: "318,224", color: "#60a5fa" },
  { label: "QUERIES/MIN",  val: "47",      color: "#4ade80" },
  { label: "CACHE_HIT",    val: "91.4%",   color: "#a78bfa" },
];

function Bar({ label, pct, color }: { label: string; pct: number; color: string }) {
  const [width, setWidth] = useState(0);
  useEffect(() => { const t = setTimeout(() => setWidth(pct), 400); return () => clearTimeout(t); }, [pct]);
  return (
    <div className="mb-3">
      <div className="flex justify-between mb-1">
        <span className="text-[9px] font-mono text-gray-500">{label}</span>
        <span className="text-[9px] font-mono" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-[3px] bg-gray-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-1000"
          style={{ width: `${width}%`, background: `linear-gradient(90deg, ${color}80, ${color})`, boxShadow: `0 0 6px ${color}60` }}
        />
      </div>
    </div>
  );
}

export default function SideHUD() {
  const [uptime, setUptime] = useState("09:42:17");
  useEffect(() => {
    let s = 9 * 3600 + 42 * 60 + 17;
    const iv = setInterval(() => {
      s++;
      const h = String(Math.floor(s / 3600)).padStart(2, "0");
      const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
      const sec = String(s % 60).padStart(2, "0");
      setUptime(`${h}:${m}:${sec}`);
    }, 1000);
    return () => clearInterval(iv);
  }, []);

  return (
    <>
      {/* LEFT PANEL */}
      <div
        className="absolute left-4 top-1/2 -translate-y-1/2 w-36 hidden xl:block pointer-events-none"
        style={{ animation: "slide-in-left 0.8s ease both 0.6s" }}
      >
        <div className="rounded-xl border border-cyan-500/12 bg-gray-950/70 backdrop-blur-sm p-4">
          <div className="flex items-center gap-1.5 mb-4">
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" style={{ boxShadow: "0 0 6px #22d3ee" }} />
            <span className="text-[9px] font-mono font-bold text-cyan-400/60 tracking-widest">SYS_METRICS</span>
          </div>

          {LEFT_METRICS.map(m => <Bar key={m.label} {...m} />)}

          <div className="mt-4 pt-3 border-t border-gray-800">
            <div className="text-[8px] font-mono text-gray-600 mb-1">UPTIME</div>
            <div className="text-[11px] font-mono text-cyan-400/70 tabular-nums">{uptime}</div>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-1">
            {["SECURE","ONLINE","AES256","JWT_OK"].map(s => (
              <span key={s} className="text-[7px] font-mono text-center py-0.5 rounded border border-gray-700/50 text-gray-600">
                {s}
              </span>
            ))}
          </div>
        </div>

        {/* Connector line to main content */}
        <div className="absolute right-0 top-1/2 w-4 h-px bg-gradient-to-r from-cyan-500/20 to-transparent" />
      </div>

      {/* RIGHT PANEL */}
      <div
        className="absolute right-4 top-1/2 -translate-y-1/2 w-36 hidden xl:block pointer-events-none"
        style={{ animation: "slide-in-right 0.8s ease both 0.7s" }}
      >
        <div className="rounded-xl border border-indigo-500/12 bg-gray-950/70 backdrop-blur-sm p-4">
          <div className="flex items-center gap-1.5 mb-4">
            <div className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" style={{ boxShadow: "0 0 6px #818cf8" }} />
            <span className="text-[9px] font-mono font-bold text-indigo-400/60 tracking-widest">GRAPH_DB</span>
          </div>

          {RIGHT_STATS.map(r => (
            <div key={r.label} className="mb-3.5">
              <div className="text-[8px] font-mono text-gray-600 mb-0.5">{r.label}</div>
              <div className="text-[13px] font-mono font-bold tabular-nums" style={{ color: r.color }}>{r.val}</div>
            </div>
          ))}

          <div className="mt-2 pt-3 border-t border-gray-800 space-y-1.5">
            {[
              { dot: "#4ade80", label: "NEO4J BOLT" },
              { dot: "#60a5fa", label: "MILVUS gRPC" },
              { dot: "#a78bfa", label: "LLM_API  SSE" },
            ].map(({ dot, label }) => (
              <div key={label} className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full animate-pulse flex-shrink-0" style={{ background: dot, boxShadow: `0 0 4px ${dot}` }} />
                <span className="text-[8px] font-mono text-gray-600">{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Connector line to main content */}
        <div className="absolute left-0 top-1/2 w-4 h-px bg-gradient-to-l from-indigo-500/20 to-transparent" />
      </div>
    </>
  );
}
