"use client";

import { BrainCircuit, Activity, Database, Network, Cpu } from "lucide-react";

const FEATURES = [
  { Icon: Network,   text: "GraphRAG 四策略混合检索" },
  { Icon: Database,  text: "Neo4j + Milvus 双库融合" },
  { Icon: Activity,  text: "LangGraph ReAct 多跳推理" },
  { Icon: Cpu,       text: "全链路 LLM 可观测性追踪" },
];

export default function LoginInfoPanel({ tick }: { tick: string }) {
  return (
    <div className="hidden lg:flex flex-col justify-between p-8 border-r border-white/[0.04] bg-gradient-to-b from-gray-900/50 to-gray-950/30">
      <div>
        <div className="relative inline-flex items-center justify-center w-20 h-20 mb-6">
          <div className="absolute inset-0 border border-cyan-500/25 rounded-full" style={{ animation: "spin-slow 12s linear infinite" }} />
          <div className="absolute inset-1.5 border border-indigo-400/20 rounded-full" style={{ animation: "spin-slow 8s linear infinite reverse" }} />
          <span className="absolute inset-0 rounded-full" style={{ boxShadow: "0 0 0 1px rgba(34,211,238,0.15)", animation: "pulse-ring 2.4s ease-out infinite" }} />
          <div className="relative w-14 h-14 rounded-2xl bg-gray-900 border border-cyan-500/40 flex items-center justify-center"
               style={{ boxShadow: "0 0 28px rgba(34,211,238,0.2),inset 0 0 16px rgba(34,211,238,0.06)" }}>
            <BrainCircuit size={28} className="text-cyan-400" />
          </div>
        </div>

        <div className="text-[9px] font-mono font-bold tracking-[0.28em] text-cyan-400/50 uppercase mb-2">
          COMAC · 商用飞机有限责任公司
        </div>
        <h1 className="text-2xl font-bold mb-1 leading-tight" style={{
          backgroundImage: "linear-gradient(135deg,#e2e8f0 0%,#38bdf8 45%,#818cf8 100%)",
          backgroundClip: "text", WebkitBackgroundClip: "text", color: "transparent",
          backgroundSize: "200% 200%", animation: "gradient-sweep 5s ease infinite",
        }}>
          航空工艺<br />知识库系统
        </h1>
        <p className="text-xs text-gray-600 mb-8">CPS GraphRAG 规范智能检索与问答平台</p>

        <div className="space-y-3">
          {FEATURES.map(({ Icon, text }, i) => (
            <div key={i} className="flex items-center gap-3 group"
                 style={{ animation: `slide-in-left 0.45s ease both ${400 + i * 80}ms` }}>
              <div className="w-7 h-7 rounded-lg bg-cyan-500/8 border border-cyan-500/15 flex items-center justify-center flex-shrink-0
                              group-hover:border-cyan-500/35 group-hover:bg-cyan-500/12 transition-all">
                <Icon size={13} className="text-cyan-400/60 group-hover:text-cyan-400 transition-colors" />
              </div>
              <span className="text-xs text-gray-500 group-hover:text-gray-300 transition-colors">{text}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-8 pt-5 border-t border-white/[0.04]">
        <div className="grid grid-cols-2 gap-2 mb-3">
          {[
            { label: "API_STATUS", val: "ONLINE",    color: "#4ade80" },
            { label: "ENCRYPT",    val: "TLS_1.3",   color: "#22d3ee" },
            { label: "AUTH_MODE",  val: "JWT_RS256",  color: "#60a5fa" },
            { label: "SYS_CLK",    val: tick,         color: "#a78bfa" },
          ].map(({ label, val, color }) => (
            <div key={label} className="rounded-lg bg-gray-900/60 border border-gray-800/60 px-2.5 py-2">
              <div className="text-[7px] font-mono text-gray-700 mb-0.5">{label}</div>
              <div className="text-[10px] font-mono font-bold tabular-nums" style={{ color }}>{val}</div>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" style={{ boxShadow: "0 0 6px #4ade80" }} />
          <span className="text-[9px] font-mono text-gray-600">ALL SYSTEMS NOMINAL</span>
        </div>
      </div>
    </div>
  );
}
