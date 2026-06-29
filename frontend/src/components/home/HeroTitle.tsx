"use client";

import { useEffect, useState } from "react";

const LINES = [
  "航空工艺规范 GraphRAG 智能问答系统",
  "知识图谱驱动的工程数据智能检索",
  "基于 Neo4j + Milvus 的多模态知识引擎",
  "涵盖 ATA 100 全谱系工艺规范知识库",
];

export default function HeroTitle() {
  const [idx, setIdx] = useState(0);
  const [text, setText] = useState("");
  const [phase, setPhase] = useState<"type" | "pause" | "erase">("type");

  useEffect(() => {
    const target = LINES[idx];
    let t: ReturnType<typeof setTimeout>;
    if (phase === "type") {
      if (text.length < target.length) {
        t = setTimeout(() => setText(target.slice(0, text.length + 1)), 50);
      } else {
        t = setTimeout(() => setPhase("pause"), 2400);
      }
    } else if (phase === "pause") {
      t = setTimeout(() => setPhase("erase"), 400);
    } else {
      if (text.length > 0) {
        t = setTimeout(() => setText(text.slice(0, -1)), 22);
      } else {
        setIdx((i) => (i + 1) % LINES.length);
        setPhase("type");
      }
    }
    return () => clearTimeout(t);
  }, [text, phase, idx]);

  return (
    <div className="text-center" style={{ animation: "slide-up-fade 0.7s ease both" }}>

      {/* Live badge */}
      <div className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 rounded-full
                      border border-cyan-500/30 bg-cyan-500/6 text-cyan-400 text-xs tracking-widest uppercase">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full rounded-full bg-cyan-400"
                style={{ animation: "pulse-ring 1.8s ease-out infinite" }} />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
        </span>
        系统在线 · 商飞大模型 v1.1.0
        <span className="w-px h-3 bg-cyan-500/40 mx-1" />
        <span className="text-cyan-500/70 font-mono">SYS_OK</span>
      </div>

      {/* Main title with glitch layers */}
      <h1 className="relative text-5xl md:text-6xl font-extrabold mb-5 tracking-tight leading-tight select-none">
        {/* Base gradient layer */}
        <span
          className="bg-gradient-to-r from-cyan-300 via-blue-400 to-indigo-400 bg-clip-text text-transparent"
          style={{ backgroundSize: "200% 200%", animation: "gradient-sweep 5s ease infinite" }}
        >
          CPS 知识库
        </span>
        {/* Glitch layer A — cyan tint */}
        <span
          aria-hidden
          className="absolute inset-0 bg-gradient-to-r from-cyan-400 to-cyan-300 bg-clip-text text-transparent"
          style={{ animation: "glitch-a 6s step-end infinite 0.5s" }}
        >
          CPS 知识库
        </span>
        {/* Glitch layer B — purple tint */}
        <span
          aria-hidden
          className="absolute inset-0 bg-gradient-to-r from-violet-400 to-purple-300 bg-clip-text text-transparent"
          style={{ animation: "glitch-b 6s step-end infinite 1.1s" }}
        >
          CPS 知识库
        </span>
      </h1>

      {/* Holographic hex decoration */}
      <div className="flex justify-center items-center gap-3 mb-5">
        <div className="h-px w-16 bg-gradient-to-r from-transparent to-cyan-500/50" />
        <div className="relative w-12 h-12 flex items-center justify-center">
          {/* Outer ring — slow spin */}
          <div className="absolute inset-0 border border-cyan-400/30 rounded-full"
               style={{ animation: "spin-slow 12s linear infinite" }}>
            <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-cyan-400/80" />
          </div>
          {/* Middle ring — counter-spin */}
          <div className="absolute inset-[18%] border border-blue-400/40 rounded-full"
               style={{ animation: "spin-slow 8s linear infinite reverse" }}>
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-1/2 w-1 h-1 rounded-full bg-blue-400/80" />
          </div>
          {/* Center dot */}
          <div className="w-2 h-2 rounded-full bg-cyan-400"
               style={{ boxShadow: "0 0 8px rgba(34,211,238,0.9), 0 0 24px rgba(34,211,238,0.4)" }} />
        </div>
        <div className="h-px w-16 bg-gradient-to-l from-transparent to-cyan-500/50" />
      </div>

      {/* Typewriter subtitle */}
      <p className="h-7 text-base md:text-lg text-gray-300 font-mono tracking-wide">
        {text}
        <span
          className="inline-block w-0.5 h-5 bg-cyan-400 ml-0.5 align-middle"
          style={{ animation: "blink-cursor 1s step-end infinite" }}
        />
      </p>

      {/* HUD status row */}
      <div className="flex items-center justify-center gap-4 mt-4 text-[10px] font-mono text-gray-600">
        {[
          { label: "NEO4J", color: "#4ade80" },
          { label: "MILVUS", color: "#60a5fa" },
          { label: "LLM_API", color: "#a78bfa" },
          { label: "REDIS", color: "#fb923c" },
        ].map(({ label, color }) => (
          <span key={label} className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}
