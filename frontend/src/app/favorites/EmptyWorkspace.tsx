"use client";

import Link from "next/link";
import { BookOpen, FileText, MessageSquare, Star } from "lucide-react";

const EXAMPLES = [
  { Icon: BookOpen,     color: "text-indigo-400", title: "4.3.2 铆接工艺参数要求",         sub: "CPS-HY-0412 · 第 4 章",    note: "常用参数，快速对照" },
  { Icon: FileText,     color: "text-green-400",  title: "航空工艺规范 · 复合材料铺层标准", sub: "CPS-CM-2201",               note: "当前项目主要规范" },
  { Icon: MessageSquare,color: "text-amber-400",  title: "复合材料固化温度范围是多少？",    sub: "常用问题",                   note: "" },
];

export function EmptyWorkspace() {
  return (
    <div style={{ animation: "slide-up-fade 0.6s ease both" }}>
      <div className="text-center mb-6">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 mb-3">
          <Star size={20} className="text-amber-400 fill-amber-400/30" />
        </div>
        <p className="text-sm font-medium text-gray-300">工作区还是空的</p>
        <p className="text-xs text-gray-600 mt-1">在问答页面或文档库中点击 ★ 即可收藏到这里</p>
      </div>

      <div className="text-xs text-gray-600 uppercase tracking-wider mb-3 px-1">示例收藏（仅预览）</div>
      <div className="space-y-2.5 pointer-events-none select-none">
        {EXAMPLES.map((ex, i) => (
          <div key={i} className="relative bg-gray-900/60 border border-gray-800/60 rounded-xl p-4 opacity-60">
            <span className="absolute top-3 right-3 text-[9px] px-1.5 py-0.5 bg-gray-800 text-gray-600 rounded-full border border-gray-700">示例</span>
            <div className="flex items-start gap-3">
              <ex.Icon size={14} className={`${ex.color} shrink-0 mt-0.5`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-300 truncate">{ex.title}</div>
                <div className="text-xs text-gray-600 mt-0.5 font-mono">{ex.sub}</div>
                {ex.note && <div className="text-xs text-gray-600 italic mt-1">{ex.note}</div>}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-3 mt-6">
        <Link href="/query"
          className="flex-1 text-center py-2 text-xs bg-indigo-600/20 border border-indigo-600/30 text-indigo-400 rounded-lg hover:bg-indigo-600/30 transition-colors">
          去问答页面
        </Link>
        <Link href="/library"
          className="flex-1 text-center py-2 text-xs bg-gray-800/60 border border-gray-700/60 text-gray-400 rounded-lg hover:bg-gray-800 transition-colors">
          去文档库
        </Link>
      </div>
    </div>
  );
}
