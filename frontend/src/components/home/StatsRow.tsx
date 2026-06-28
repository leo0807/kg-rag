"use client";

import { useEffect, useRef, useState } from "react";

const STATS = [
  { label: "图谱节点", value: 42000, suffix: "+",  decimals: 0, color: "#22d3ee" },
  { label: "技术规范", value: 318,   suffix: "份",  decimals: 0, color: "#60a5fa" },
  { label: "处理查询", value: 8200,  suffix: "+",  decimals: 0, color: "#818cf8" },
  { label: "系统可用性", value: 99.9, suffix: "%", decimals: 1, color: "#4ade80" },
];

function useCountUp(target: number, decimals: number) {
  const [val, setVal] = useState(0);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    let raf: number;
    let startTs: number;
    const DURATION = 1600;

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

function Stat({ label, value, suffix, decimals, color, delay }: typeof STATS[0] & { delay: number }) {
  const v = useCountUp(value, decimals);
  return (
    <div
      className="relative border border-gray-700/40 bg-gray-900/50 backdrop-blur-sm rounded-xl p-5 text-center overflow-hidden group hover:border-opacity-80 transition-all duration-300"
      style={{
        animation: `slide-up-fade 0.6s ease both`,
        animationDelay: `${delay}ms`,
        borderColor: `${color}20`,
      }}
    >
      {/* Corner glow on hover */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none rounded-xl"
        style={{ background: `radial-gradient(circle at 50% 0%, ${color}18 0%, transparent 70%)` }}
      />
      <div className="text-3xl font-bold font-mono" style={{ color }}>
        {decimals > 0 ? v.toFixed(decimals) : Math.floor(v).toLocaleString()}
        {suffix}
      </div>
      <div className="text-xs text-gray-500 mt-1.5 tracking-wide">{label}</div>
    </div>
  );
}

export default function StatsRow() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 w-full max-w-2xl mx-auto">
      {STATS.map((s, i) => (
        <Stat key={s.label} {...s} delay={300 + i * 80} />
      ))}
    </div>
  );
}
