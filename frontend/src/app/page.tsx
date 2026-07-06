"use client";

import dynamic from "next/dynamic";
import HeroTitle   from "@/components/home/HeroTitle";
import StatsRow    from "@/components/home/StatsRow";
import FeatureGrid from "@/components/home/FeatureGrid";
import CtaButton   from "@/components/home/CtaButton";
import TickerBanner from "@/components/home/TickerBanner";

// 重型 canvas / 动画组件懒加载，不阻塞首屏渲染
const ParticleCanvas = dynamic(() => import("@/components/home/ParticleCanvas"), { ssr: false });
const FloatingData   = dynamic(() => import("@/components/home/FloatingData"),   { ssr: false });
const SideHUD        = dynamic(() => import("@/components/home/SideHUD"),        { ssr: false });

export default function HomePage() {
  return (
    <div className="relative min-h-screen bg-gray-950 flex flex-col items-center justify-center overflow-hidden px-5 py-14 pb-20">

      {/* ── 背景层（由远到近）────────────────────── */}

      {/* 六边形网格 */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.055]" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='56' height='100' viewBox='0 0 56 100'%3E%3Cpath d='M28 66L0 50V18L28 2l28 16v32L28 66zm0 0v34' fill='none' stroke='%2322d3ee' stroke-width='0.5'/%3E%3C/svg%3E")`,
        backgroundSize: "56px 100px",
      }} />

      {/* 浮动数据流 */}
      <FloatingData />

      {/* 粒子网络 */}
      <ParticleCanvas />

      {/* 中心辉光 */}
      <div className="absolute pointer-events-none" style={{
        top: "32%", left: "50%", transform: "translate(-50%,-50%)",
        width: "760px", height: "440px",
        background: "radial-gradient(ellipse, rgba(27,107,181,0.2) 0%, rgba(99,102,241,0.08) 50%, transparent 70%)",
      }} />

      {/* 全屏扫描线 */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute left-0 right-0 h-[2px]" style={{
          background: "linear-gradient(90deg,transparent 0%,rgba(34,211,238,0.4) 40%,rgba(34,211,238,0.4) 60%,transparent 100%)",
          boxShadow: "0 0 14px rgba(34,211,238,0.3)",
          animation: "scanline 9s ease-in-out infinite",
        }} />
      </div>

      {/* 顶/底光条 */}
      <div className="absolute top-0 left-0 right-0 h-px pointer-events-none"
           style={{ background: "linear-gradient(90deg,transparent,rgba(34,211,238,0.65) 50%,transparent)" }} />
      <div className="absolute bottom-0 left-0 right-0 h-px pointer-events-none"
           style={{ background: "linear-gradient(90deg,transparent,rgba(99,102,241,0.4) 50%,transparent)" }} />

      {/* 顶部分类条 */}
      <div className="absolute top-0 left-0 right-0 h-6 flex items-center justify-center gap-4 pointer-events-none z-10"
           style={{ background: "rgba(2,8,20,0.7)", borderBottom: "1px solid rgba(34,211,238,0.1)" }}>
        {["COMAC INTERNAL", "CPS-GRAPHRAG-SYS", "SEC-LEVEL-2", "ATA100 SPEC", "NOT FOR DISTRIBUTION"].map((t, i) => (
          <span key={i} className="text-[8px] font-mono text-gray-700 tracking-widest hidden sm:inline">{t}</span>
        ))}
      </div>

      {/* ── HUD 角框 ─────────────────────────────── */}
      {[
        { pos:"top-5 left-5",    br:"border-l-2 border-t-2", label:"CPS//SYS",  lPos:"mt-1",       ta:"" },
        { pos:"top-5 right-5",   br:"border-r-2 border-t-2", label:"v1.1.0",    lPos:"mt-1",       ta:"text-right" },
        { pos:"bottom-5 left-5", br:"border-l-2 border-b-2", label:"COMAC",     lPos:"mb-1 order-first", ta:"" },
        { pos:"bottom-5 right-5",br:"border-r-2 border-b-2", label:"SECURE",    lPos:"mb-1 order-first", ta:"text-right" },
      ].map(({ pos, br, label, lPos, ta }, i) => (
        <div key={i} className={`absolute ${pos} pointer-events-none flex flex-col`}
             style={{ animation: `corner-appear 0.8s ease both ${300 + i * 80}ms` }}>
          <div className={`w-10 h-10 ${br} border-cyan-400/35`} />
          <span className={`${lPos} text-[8px] font-mono text-cyan-500/35 tracking-widest ${ta}`}>{label}</span>
        </div>
      ))}

      {/* ── 雷达（右上，绝对定位）─────────────────── */}
      <div className="absolute top-8 right-24 pointer-events-none hidden lg:block"
           style={{ animation: "corner-appear 1s ease both 0.9s" }}>
        <div className="relative w-24 h-24 opacity-[0.22]">
          <div className="absolute inset-0 border border-cyan-500/70 rounded-full" />
          <div className="absolute inset-[22%] border border-cyan-500/50 rounded-full" />
          <div className="absolute inset-[44%] border border-cyan-500/40 rounded-full" />
          <div className="absolute inset-[62%] bg-cyan-400/70 rounded-full" />
          <div className="absolute top-1/2 left-0 right-0 h-px bg-cyan-500/30" />
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-cyan-500/30" />
          <div className="absolute inset-0 rounded-full overflow-hidden" style={{ animation: "radar-sweep 4s linear infinite" }}>
            <div className="absolute top-1/2 left-1/2 w-12 h-px origin-left"
                 style={{ background: "linear-gradient(90deg,rgba(34,211,238,0.9),transparent)" }} />
            <div className="absolute inset-0" style={{
              background: "conic-gradient(from 0deg,rgba(34,211,238,0.18) 0deg,transparent 65deg)",
            }} />
          </div>
        </div>
        <div className="mt-1 text-center">
          <span className="text-[7px] font-mono text-cyan-500/30 tracking-widest">SCAN_ACTIVE</span>
        </div>
      </div>

      {/* ── 侧边 HUD ─────────────────────────────── */}
      <SideHUD />

      {/* ── 底部 ticker ──────────────────────────── */}
      <TickerBanner />

      {/* ── 主内容区 ─────────────────────────────── */}
      <div className="relative z-10 flex flex-col items-center gap-10 w-full max-w-3xl">
        <HeroTitle />
        <StatsRow />
        <FeatureGrid />
        <CtaButton />

        <p className="text-[10px] text-gray-700 tracking-[0.22em] font-mono"
           style={{ animation: "slide-up-fade 0.6s ease 1s both" }}>
          商用飞机有限责任公司 · 航空工艺规范知识图谱 · <span className="text-gray-600">CLASSIFIED</span>
        </p>
      </div>
    </div>
  );
}
