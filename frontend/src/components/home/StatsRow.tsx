"use client";

import { useEffect, useRef, useState } from "react";

const STATS = [
  { label: "GRAPH_NODES",  value: 42000, suffix: "+",  decimals: 0, color: "#22d3ee", tag: "NEO4J" },
  { label: "SPEC_DOCS",    value: 318,   suffix: "",   decimals: 0, color: "#60a5fa", tag: "LIBRARY" },
  { label: "QUERIES_PROC", value: 8200,  suffix: "+",  decimals: 0, color: "#818cf8", tag: "LLM" },
  { label: "SYS_UPTIME",   value: 99.9,  suffix: "%",  decimals: 1, color: "#4ade80", tag: "INFRA" },
];

function useCountUp(target: number, decimals: number) {
  const [val, setVal] = useState(0);
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let raf: number;
    let startTs: number;
    const DURATION = 1800;
    function step(ts: number) {
      if (!startTs) startTs = ts;
      const p = Math.min((ts - startTs) / DURATION, 1);
      const eased = 1 - (1 - p) ** 3;
      setVal(parseFloat((eased * target).toFixed(decimals)));
      if (p < 1) raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, decimals]);
  return val;
}

function StatCard({ label, value, suffix, decimals, color, tag, delay }: typeof STATS[0] & { delay: number }) {
  const v = useCountUp(value, decimals);
  const display = decimals > 0 ? v.toFixed(decimals) : Math.floor(v).toLocaleString();

  return (
    <div
      className="relative rounded-xl overflow-hidden border border-gray-800/80 bg-gray-950 p-5 group hover:border-opacity-60 transition-all duration-500"
      style={{
        animation: `scale-fade 0.5s cubic-bezier(0.34,1.56,0.64,1) both ${delay}ms`,
        borderColor: `${color}18`,
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = `0 0 28px ${color}22, inset 0 0 20px ${color}08`;
        (e.currentTarget as HTMLDivElement).style.borderColor = `${color}40`;
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = "";
        (e.currentTarget as HTMLDivElement).style.borderColor = `${color}18`;
      }}
    >
      {/* Corner tag */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-[8px] font-mono tracking-widest text-gray-700 group-hover:text-gray-500 transition-colors">{tag}</span>
        <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
      </div>

      {/* Value */}
      <div className="font-mono font-bold tabular-nums leading-none mb-1" style={{ fontSize: "1.9rem", color }}>
        {display}{suffix}
      </div>

      {/* Label */}
      <div className="text-[10px] font-mono text-gray-600 tracking-widest mt-2">{label}</div>

      {/* Bottom bar */}
      <div className="absolute bottom-0 left-0 right-0 h-[2px]"
           style={{ background: `linear-gradient(90deg, transparent, ${color}40, transparent)` }} />

      {/* Scan line on hover */}
      <div
        className="absolute inset-x-0 h-[1px] top-0 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity"
        style={{ background: `linear-gradient(90deg, transparent, ${color}70, transparent)`, animation: "scan-down 2.5s linear infinite" }}
      />

      {/* Corner brackets */}
      <div className="absolute top-2 left-2 w-2.5 h-2.5 border-l border-t opacity-20 group-hover:opacity-60 transition-opacity" style={{ borderColor: color }} />
      <div className="absolute bottom-2 right-2 w-2.5 h-2.5 border-r border-b opacity-20 group-hover:opacity-60 transition-opacity" style={{ borderColor: color }} />
    </div>
  );
}

export default function StatsRow() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 w-full max-w-2xl mx-auto">
      {STATS.map((s, i) => (
        <StatCard key={s.label} {...s} delay={320 + i * 90} />
      ))}
    </div>
  );
}
