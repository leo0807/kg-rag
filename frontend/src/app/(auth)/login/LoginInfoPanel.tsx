"use client";

import { useEffect, useState } from "react";
import { BrainCircuit, Activity, Database, Network, Cpu } from "lucide-react";

const FEATURES = [
  { Icon: Network,   text: "GraphRAG 四策略混合检索" },
  { Icon: Database,  text: "Neo4j + Milvus 双库融合" },
  { Icon: Activity,  text: "LangGraph ReAct 多跳推理" },
  { Icon: Cpu,       text: "全链路 LLM 可观测性追踪" },
];

const TELEMETRY = [
  { label: "API_STATUS", val: "ONLINE",   color: "#4ade80", pct: 100 },
  { label: "ENCRYPT",    val: "TLS_1.3",  color: "#22d3ee", pct: 92  },
  { label: "AUTH_MODE",  val: "JWT_RS256", color: "#60a5fa", pct: 85  },
  { label: "SYS_CLK",   val: null,        color: "#a78bfa", pct: 70  },
];

const SEC_LOGS = [
  "INIT: 会话密钥交换完成",
  "AUTH: 接收到用户身份请求",
  "DB  : NEO4J 连接池已就绪",
  "TLS : 握手协议验证通过",
  "SCAN: 威胁态势感知正常",
  "LOG : 审计记录通道开启",
];

function Radar() {
  return (
    <div className="absolute top-7 right-7 opacity-30 pointer-events-none">
      <div className="relative w-14 h-14">
        <div className="absolute inset-0 border border-cyan-400/70 rounded-full" />
        <div className="absolute inset-[25%] border border-cyan-400/50 rounded-full" />
        <div className="absolute inset-[50%] border border-cyan-400/40 rounded-full" />
        <div className="absolute inset-[68%] bg-cyan-400/80 rounded-full" />
        <div className="absolute top-1/2 left-0 right-0 h-px bg-cyan-400/25" />
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-cyan-400/25" />
        <div className="absolute inset-0 rounded-full overflow-hidden" style={{ animation: "radar-sweep 3s linear infinite" }}>
          <div className="absolute top-1/2 left-1/2 w-7 h-px origin-left"
               style={{ background: "linear-gradient(90deg,rgba(34,211,238,0.9),transparent)" }} />
          <div className="absolute inset-0"
               style={{ background: "conic-gradient(from 0deg,rgba(34,211,238,0.2) 0deg,transparent 55deg)" }} />
        </div>
        {/* Blip */}
        <div className="absolute w-1 h-1 rounded-full bg-cyan-300"
             style={{ top: "30%", left: "65%", boxShadow: "0 0 4px #22d3ee", animation: "pulse-ring 2s ease-out infinite" }} />
      </div>
      <div className="text-[7px] font-mono text-cyan-500/30 tracking-widest text-center mt-0.5">SCAN</div>
    </div>
  );
}

export default function LoginInfoPanel({ tick }: { tick: string }) {
  const [logIdx, setLogIdx] = useState(0);
  const [bars, setBars] = useState([0, 0, 0, 0]);

  useEffect(() => {
    const t = setTimeout(() => setBars([100, 92, 85, 70]), 400);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    const iv = setInterval(() => setLogIdx(i => (i + 1) % SEC_LOGS.length), 2200);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="relative hidden lg:flex flex-col justify-between p-8 border-r border-white/[0.04] bg-gradient-to-b from-gray-900/50 to-gray-950/30 overflow-hidden">
      <Radar />

      {/* Subtle inner scan line */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute left-0 right-0 h-px opacity-30" style={{
          background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.5) 50%,transparent)",
          animation: "scan-down 6s linear infinite",
        }} />
      </div>

      <div>
        {/* Logo */}
        <div className="relative inline-flex items-center justify-center w-20 h-20 mb-6">
          <div className="absolute inset-0 border border-cyan-500/25 rounded-full" style={{ animation: "spin-slow 12s linear infinite" }} />
          <div className="absolute inset-1.5 border border-indigo-400/20 rounded-full" style={{ animation: "spin-slow 8s linear infinite reverse" }} />
          <div className="absolute inset-3 border border-cyan-400/10 rounded-full" style={{ animation: "spin-slow 5s linear infinite" }} />
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
        <p className="text-xs text-gray-600 mb-6">CPS GraphRAG 规范智能检索与问答平台</p>

        {/* Feature list */}
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

      {/* Telemetry grid */}
      <div className="mt-6 pt-5 border-t border-white/[0.04]">
        <div className="grid grid-cols-2 gap-2 mb-3">
          {TELEMETRY.map(({ label, val, color }, i) => (
            <div key={label} className="rounded-lg bg-gray-900/60 border border-gray-800/60 px-2.5 py-2">
              <div className="text-[7px] font-mono text-gray-700 mb-0.5">{label}</div>
              <div className="text-[10px] font-mono font-bold tabular-nums" style={{ color }}>
                {val ?? tick}
              </div>
              <div className="mt-1.5 h-[2px] bg-gray-800 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-1000"
                     style={{ width: `${bars[i]}%`, background: color, boxShadow: `0 0 4px ${color}60`, transitionDelay: `${i * 120}ms` }} />
              </div>
            </div>
          ))}
        </div>

        {/* Security log */}
        <div className="rounded-lg bg-gray-950/80 border border-gray-800/50 px-3 py-2 mb-3">
          <div className="text-[7px] font-mono text-gray-700 mb-1.5 tracking-widest">SEC_LOG</div>
          {SEC_LOGS.slice(logIdx, logIdx + 3).concat(
            SEC_LOGS.slice(0, Math.max(0, logIdx + 3 - SEC_LOGS.length))
          ).map((log, i) => (
            <div key={i} className="flex items-center gap-1.5 mb-1 last:mb-0 transition-opacity duration-500"
                 style={{ opacity: i === 0 ? 1 : i === 1 ? 0.6 : 0.3 }}>
              <span className="text-cyan-500/40 text-[8px]">›</span>
              <span className="text-[8px] font-mono text-gray-600">{log}</span>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" style={{ boxShadow: "0 0 6px #4ade80" }} />
          <span className="text-[9px] font-mono text-gray-600">ALL SYSTEMS NOMINAL</span>
          <div className="flex-1 h-px bg-gradient-to-r from-emerald-500/10 to-transparent" />
          <span className="text-[7px] font-mono text-gray-700">T+{tick}</span>
        </div>
      </div>
    </div>
  );
}
