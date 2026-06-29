"use client";

import Link from "next/link";
import {
  MessageSquare, Network, BookOpen, Activity,
  BarChart3, Cpu, Shield, Layers, GitBranch, Mic,
} from "lucide-react";

const FEATURES = [
  { icon: MessageSquare, label: "智能问答",  desc: "GraphRAG 四策略检索", href: "/query",
    glow: "rgba(34,211,238,0.2)",  border: "rgba(34,211,238,0.18)", hborder: "rgba(34,211,238,0.6)", iconColor: "#22d3ee" },
  { icon: Network,       label: "图谱探索",  desc: "知识图谱可视化导览", href: "/graph",
    glow: "rgba(129,140,248,0.2)", border: "rgba(129,140,248,0.18)", hborder: "rgba(129,140,248,0.6)", iconColor: "#818cf8" },
  { icon: BookOpen,      label: "文档库",    desc: "航空工艺规范管理",   href: "/library",
    glow: "rgba(74,222,128,0.18)", border: "rgba(74,222,128,0.18)", hborder: "rgba(74,222,128,0.6)", iconColor: "#4ade80" },
  { icon: Activity,      label: "仿真集成",  desc: "工艺仿真参数接口",   href: "/simulation",
    glow: "rgba(251,146,60,0.18)", border: "rgba(251,146,60,0.18)", hborder: "rgba(251,146,60,0.6)", iconColor: "#fb923c" },
  { icon: BarChart3,     label: "数据分析",  desc: "可视化报表与统计",   href: "/analytics",
    glow: "rgba(96,165,250,0.18)", border: "rgba(96,165,250,0.18)", hborder: "rgba(96,165,250,0.6)", iconColor: "#60a5fa" },
  { icon: GitBranch,     label: "图谱 Diff", desc: "章节级版本变更追踪", href: "/graph",
    glow: "rgba(244,114,182,0.18)", border: "rgba(244,114,182,0.18)", hborder: "rgba(244,114,182,0.6)", iconColor: "#f472b6" },
  { icon: Shield,        label: "合规管理",  desc: "适航条款合规矩阵",   href: "/admin",
    glow: "rgba(251,191,36,0.18)", border: "rgba(251,191,36,0.18)", hborder: "rgba(251,191,36,0.6)", iconColor: "#fbbf24" },
  { icon: Layers,        label: "供应链图谱", desc: "BOM · 供应商 · CAD", href: "/graph",
    glow: "rgba(52,211,153,0.18)", border: "rgba(52,211,153,0.18)", hborder: "rgba(52,211,153,0.6)", iconColor: "#34d399" },
  { icon: Mic,           label: "语音问答",  desc: "实时语音交互接口",   href: "/query",
    glow: "rgba(167,139,250,0.18)", border: "rgba(167,139,250,0.18)", hborder: "rgba(167,139,250,0.6)", iconColor: "#a78bfa" },
  { icon: Cpu,           label: "AI 实验室", desc: "模型评测与微调管理", href: "/admin/lab",
    glow: "rgba(248,113,113,0.18)", border: "rgba(248,113,113,0.18)", hborder: "rgba(248,113,113,0.6)", iconColor: "#f87171" },
];

const IDX = ["01","02","03","04","05","06","07","08","09","10"];

export default function FeatureGrid() {
  return (
    <div
      className="grid grid-cols-2 md:grid-cols-5 gap-2.5 w-full max-w-3xl mx-auto"
      style={{ animation: "slide-up-fade 0.7s ease 0.55s both" }}
    >
      {FEATURES.map((f, i) => (
        <Link
          key={f.label}
          href={f.href}
          className="group relative p-4 rounded-xl bg-gray-900/50 backdrop-blur-sm border transition-all duration-300 hover:-translate-y-1 overflow-hidden"
          style={{ borderColor: f.border }}
          onMouseEnter={(e) => {
            const el = e.currentTarget as HTMLAnchorElement;
            el.style.borderColor = f.hborder;
            el.style.boxShadow = `0 0 24px ${f.glow}, inset 0 0 16px ${f.glow}`;
          }}
          onMouseLeave={(e) => {
            const el = e.currentTarget as HTMLAnchorElement;
            el.style.borderColor = f.border;
            el.style.boxShadow = "";
          }}
        >
          {/* Corner index */}
          <span className="absolute top-2 right-2 text-[9px] font-mono opacity-25 group-hover:opacity-60 transition-opacity"
                style={{ color: f.iconColor }}>
            {IDX[i]}
          </span>

          {/* Top-left corner bracket */}
          <span className="absolute top-1.5 left-1.5 w-2.5 h-2.5 border-l border-t opacity-30 group-hover:opacity-70 transition-opacity"
                style={{ borderColor: f.iconColor }} />
          {/* Bottom-right corner bracket */}
          <span className="absolute bottom-1.5 right-1.5 w-2.5 h-2.5 border-r border-b opacity-30 group-hover:opacity-70 transition-opacity"
                style={{ borderColor: f.iconColor }} />

          {/* Hover scan line */}
          <span
            className="absolute inset-x-0 h-px top-0 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity duration-300"
            style={{ background: `linear-gradient(90deg, transparent, ${f.iconColor}80, transparent)` }}
          />

          <f.icon
            size={20}
            className="mb-2.5 transition-all duration-300 group-hover:scale-110 group-hover:drop-shadow-[0_0_6px_currentColor]"
            style={{ color: f.iconColor }}
          />
          <div className="text-xs font-semibold text-gray-200 leading-tight">{f.label}</div>
          <div className="text-[10px] text-gray-600 mt-0.5 leading-snug">{f.desc}</div>
        </Link>
      ))}
    </div>
  );
}
