"use client";

import Link from "next/link";
import { ChevronRight, Lock } from "lucide-react";
import { useState } from "react";

export default function CtaButton() {
  const [hover, setHover] = useState(false);

  return (
    <div className="flex flex-col items-center gap-3" style={{ animation: "slide-up-fade 0.7s ease 0.75s both" }}>
      {/* Primary button */}
      <Link
        href="/query"
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        className="group relative inline-flex items-center gap-3 px-10 py-3.5 font-bold text-sm text-white overflow-hidden transition-all duration-300"
        style={{
          clipPath: "polygon(12px 0%, 100% 0%, calc(100% - 12px) 100%, 0% 100%)",
          background: "linear-gradient(135deg, #0891b2 0%, #2563eb 50%, #6366f1 100%)",
          boxShadow: hover
            ? "0 0 40px rgba(34,211,238,0.5), 0 0 80px rgba(34,211,238,0.2), inset 0 0 20px rgba(255,255,255,0.05)"
            : "0 0 20px rgba(34,211,238,0.2)",
          transform: hover ? "scale(1.03)" : "scale(1)",
          letterSpacing: "0.12em",
        }}
      >
        {/* Shine */}
        <span className="absolute inset-0 pointer-events-none"
          style={{ background: "linear-gradient(90deg,transparent 0%,rgba(255,255,255,0.12) 50%,transparent 100%)", backgroundSize: "200% 100%", animation: "shine 2.5s linear infinite" }} />
        {/* Scan line on hover */}
        {hover && (
          <span className="absolute inset-x-0 h-[1px] pointer-events-none"
            style={{ background: "linear-gradient(90deg,transparent,rgba(255,255,255,0.6),transparent)", animation: "scan-down 1.2s linear infinite" }} />
        )}
        <Lock size={13} className="opacity-70 group-hover:opacity-100 transition-opacity" />
        进入指挥中心
        <ChevronRight size={15} className="group-hover:translate-x-1 transition-transform" />
      </Link>

      {/* Secondary row */}
      <div className="flex items-center gap-4 text-[10px] font-mono text-gray-700">
        <Link href="/library" className="hover:text-cyan-400/70 transition-colors tracking-widest">[ 文档库 ]</Link>
        <span className="w-px h-3 bg-gray-800" />
        <Link href="/graph" className="hover:text-indigo-400/70 transition-colors tracking-widest">[ 图谱探索 ]</Link>
        <span className="w-px h-3 bg-gray-800" />
        <Link href="/analytics" className="hover:text-violet-400/70 transition-colors tracking-widest">[ 数据分析 ]</Link>
      </div>
    </div>
  );
}
