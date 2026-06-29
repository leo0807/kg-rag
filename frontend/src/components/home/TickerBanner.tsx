"use client";

const MESSAGES = [
  "NEO4J SYNC — 42,817 NODES · 318,224 RELS INDEXED",
  "MILVUS VECTOR DB HEALTHY — P95 LATENCY 12ms",
  "LLM_API THROUGHPUT: 47 REQ/MIN · SUCCESS RATE 99.6%",
  "CHAPTER ATA-20-00-00 工艺规范已同步至主图谱",
  "COMPLIANCE SCAN COMPLETE — 0 CRITICAL VIOLATIONS",
  "GRAPH DIFF ENGINE v2.1 — 新增 312 个差异节点",
  "CACHE HIT RATE 91.4% — REDIS CLUSTER OPTIMAL",
  "USER ACCESS AUDIT LOG — 今日登录 28 次 · 0 ANOMALY",
  "VECTOR INDEX REBUILT — 3.2M EMBEDDINGS · READY",
  "AUTHORIZED SESSION — CPS KNOWLEDGE GRAPH ONLINE",
];

export default function TickerBanner() {
  const repeated = [...MESSAGES, ...MESSAGES];

  return (
    <div className="absolute bottom-0 left-0 right-0 h-7 border-t z-20 overflow-hidden flex items-center pointer-events-none"
         style={{ borderColor: "rgba(34,211,238,0.12)", background: "rgba(2,8,20,0.85)" }}>
      {/* Left badge */}
      <div className="flex-shrink-0 flex items-center gap-2 px-3 border-r h-full z-10"
           style={{ borderColor: "rgba(34,211,238,0.15)", background: "rgba(2,8,20,0.95)" }}>
        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"
              style={{ boxShadow: "0 0 6px #22d3ee" }} />
        <span className="text-[8px] font-mono font-bold text-cyan-400/70 tracking-widest whitespace-nowrap">LIVE_FEED</span>
      </div>

      {/* Scrolling text */}
      <div className="flex-1 overflow-hidden relative">
        <div className="flex gap-0 whitespace-nowrap"
             style={{ animation: "ticker-scroll 60s linear infinite" }}>
          {repeated.map((msg, i) => (
            <span key={i} className="inline-flex items-center gap-2 text-[9px] font-mono text-gray-600 px-6">
              <span className="text-cyan-500/30 select-none">▶</span>
              {msg}
            </span>
          ))}
        </div>
        {/* Fade edges */}
        <div className="absolute inset-y-0 left-0 w-8 pointer-events-none"
             style={{ background: "linear-gradient(90deg, rgba(2,8,20,0.9), transparent)" }} />
        <div className="absolute inset-y-0 right-0 w-8 pointer-events-none"
             style={{ background: "linear-gradient(270deg, rgba(2,8,20,0.9), transparent)" }} />
      </div>

      {/* Right badge */}
      <div className="flex-shrink-0 flex items-center gap-2 px-3 border-l h-full"
           style={{ borderColor: "rgba(34,211,238,0.15)", background: "rgba(2,8,20,0.95)" }}>
        <span className="text-[8px] font-mono text-gray-700 tracking-widest">UTC+8</span>
      </div>
    </div>
  );
}
