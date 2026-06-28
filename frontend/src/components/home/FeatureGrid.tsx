"use client";

import Link from "next/link";
import {
  MessageSquare, Network, BookOpen, Activity,
  BarChart3, Cpu, Shield, Layers, GitBranch, Mic,
} from "lucide-react";

const FEATURES = [
  {
    icon: MessageSquare, label: "智能问答", desc: "GraphRAG 四策略检索",
    href: "/query",
    glow: "rgba(34,211,238,0.15)", border: "rgba(34,211,238,0.2)", hborder: "rgba(34,211,238,0.5)",
    iconColor: "#22d3ee",
  },
  {
    icon: Network, label: "图谱探索", desc: "知识图谱可视化导览",
    href: "/graph",
    glow: "rgba(129,140,248,0.15)", border: "rgba(129,140,248,0.2)", hborder: "rgba(129,140,248,0.5)",
    iconColor: "#818cf8",
  },
  {
    icon: BookOpen, label: "文档库", desc: "航空工艺规范管理",
    href: "/library",
    glow: "rgba(74,222,128,0.12)", border: "rgba(74,222,128,0.2)", hborder: "rgba(74,222,128,0.5)",
    iconColor: "#4ade80",
  },
  {
    icon: Activity, label: "仿真集成", desc: "工艺仿真参数接口",
    href: "/simulation",
    glow: "rgba(251,146,60,0.12)", border: "rgba(251,146,60,0.2)", hborder: "rgba(251,146,60,0.5)",
    iconColor: "#fb923c",
  },
  {
    icon: BarChart3, label: "数据分析", desc: "可视化报表与统计",
    href: "/analytics",
    glow: "rgba(96,165,250,0.12)", border: "rgba(96,165,250,0.2)", hborder: "rgba(96,165,250,0.5)",
    iconColor: "#60a5fa",
  },
  {
    icon: GitBranch, label: "图谱 Diff", desc: "章节级版本变更追踪",
    href: "/graph",
    glow: "rgba(244,114,182,0.12)", border: "rgba(244,114,182,0.2)", hborder: "rgba(244,114,182,0.5)",
    iconColor: "#f472b6",
  },
  {
    icon: Shield, label: "合规管理", desc: "适航条款合规矩阵",
    href: "/admin",
    glow: "rgba(251,191,36,0.12)", border: "rgba(251,191,36,0.2)", hborder: "rgba(251,191,36,0.5)",
    iconColor: "#fbbf24",
  },
  {
    icon: Layers, label: "供应链图谱", desc: "BOM · 供应商 · CAD",
    href: "/graph",
    glow: "rgba(52,211,153,0.12)", border: "rgba(52,211,153,0.2)", hborder: "rgba(52,211,153,0.5)",
    iconColor: "#34d399",
  },
  {
    icon: Mic, label: "语音问答", desc: "实时语音交互接口",
    href: "/query",
    glow: "rgba(167,139,250,0.12)", border: "rgba(167,139,250,0.2)", hborder: "rgba(167,139,250,0.5)",
    iconColor: "#a78bfa",
  },
  {
    icon: Cpu, label: "AI 实验室", desc: "模型评测与微调管理",
    href: "/admin/lab",
    glow: "rgba(248,113,113,0.12)", border: "rgba(248,113,113,0.2)", hborder: "rgba(248,113,113,0.5)",
    iconColor: "#f87171",
  },
];

export default function FeatureGrid() {
  return (
    <div
      className="grid grid-cols-2 md:grid-cols-5 gap-2.5 w-full max-w-3xl mx-auto"
      style={{ animation: "slide-up-fade 0.7s ease 0.55s both" }}
    >
      {FEATURES.map((f) => (
        <Link
          key={f.href + f.label}
          href={f.href}
          className="group relative p-4 rounded-xl bg-gray-900/40 backdrop-blur-sm border transition-all duration-300 hover:-translate-y-1"
          style={{ borderColor: f.border }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLAnchorElement).style.borderColor = f.hborder;
            (e.currentTarget as HTMLAnchorElement).style.boxShadow = `0 0 20px ${f.glow}`;
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLAnchorElement).style.borderColor = f.border;
            (e.currentTarget as HTMLAnchorElement).style.boxShadow = "";
          }}
        >
          <f.icon size={20} className="mb-2.5 transition-transform group-hover:scale-110" style={{ color: f.iconColor }} />
          <div className="text-xs font-semibold text-gray-200 leading-tight">{f.label}</div>
          <div className="text-[10px] text-gray-600 mt-0.5 leading-snug">{f.desc}</div>
        </Link>
      ))}
    </div>
  );
}
