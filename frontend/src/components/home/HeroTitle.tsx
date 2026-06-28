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
        t = setTimeout(() => setText(target.slice(0, text.length + 1)), 55);
      } else {
        t = setTimeout(() => setPhase("pause"), 2200);
      }
    } else if (phase === "pause") {
      t = setTimeout(() => setPhase("erase"), 400);
    } else {
      if (text.length > 0) {
        t = setTimeout(() => setText(text.slice(0, -1)), 25);
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
      <div className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 rounded-full border border-cyan-500/25 bg-cyan-500/5 text-cyan-400 text-xs tracking-widest uppercase">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full rounded-full bg-cyan-400"
                style={{ animation: "pulse-ring 1.8s ease-out infinite" }} />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-400" />
        </span>
        系统在线 · 商飞大模型 v1.1.0
      </div>

      {/* Main title */}
      <h1 className="text-5xl md:text-6xl font-extrabold mb-5 tracking-tight leading-tight">
        <span
          className="bg-gradient-to-r from-cyan-300 via-blue-400 to-indigo-400 bg-clip-text text-transparent"
          style={{
            backgroundSize: "200% 200%",
            animation: "gradient-sweep 5s ease infinite",
          }}
        >
          CPS 知识库
        </span>
      </h1>

      {/* Rotating hex decoration */}
      <div className="flex justify-center mb-5">
        <div
          className="w-12 h-12 border border-blue-500/30 rounded-lg flex items-center justify-center"
          style={{ animation: "spin-slow 12s linear infinite" }}
        >
          <div className="w-6 h-6 border border-cyan-400/60 rounded" />
        </div>
      </div>

      {/* Typewriter subtitle */}
      <p className="h-7 text-base md:text-lg text-gray-300 font-mono tracking-wide">
        {text}
        <span
          className="inline-block w-0.5 h-5 bg-cyan-400 ml-0.5 align-middle"
          style={{ animation: "blink-cursor 1s step-end infinite" }}
        />
      </p>
    </div>
  );
}
