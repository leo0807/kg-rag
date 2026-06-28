"use client";

import { usePathname } from "next/navigation";
import { useRef, useState } from "react";
import { HelpCircle } from "lucide-react";
import { META, SKIP } from "./pageMeta";

export default function PageBanner() {
  const pathname = usePathname();
  const [showTooltip, setShowTooltip] = useState(false);
  const [tipPos, setTipPos] = useState({ x: 0, y: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);

  if (SKIP.has(pathname)) return null;
  if ((pathname.startsWith("/library/") || pathname.startsWith("/wiki/")) && pathname.split("/").length > 2) return null;

  const meta = META[pathname];
  if (!meta) return null;

  const { Icon, title, desc, detail } = meta;

  function handleMouseEnter() {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    const tipWidth = 320;
    const x = Math.min(rect.left, window.innerWidth - tipWidth - 16);
    setTipPos({ x, y: rect.bottom + 8 });
    setShowTooltip(true);
  }

  return (
    <>
      <div
        suppressHydrationWarning
        className="shrink-0 flex items-center gap-3 px-5 py-2.5 border-b border-gray-800/60 bg-gray-950/80 backdrop-blur-sm"
        style={{ animation: "slide-up-fade 0.55s ease both" }}
      >
        {/* animated left accent */}
        <div
          className="w-[2px] self-stretch rounded-full bg-gradient-to-b from-cyan-500/80 via-blue-500/60 to-transparent"
          style={{ animation: "glow-pulse 2.5s ease-in-out infinite" }}
        />

        {/* icon */}
        <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center">
          <Icon size={13} className="text-cyan-400" />
        </div>

        {/* text + tooltip trigger */}
        <div className="min-w-0 flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-200 leading-none">{title}</span>
          <span className="hidden sm:block w-px h-3 bg-gray-700" />
          <span className="hidden sm:block text-xs text-gray-500 truncate">{desc}</span>

          <button
            ref={btnRef}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={() => setShowTooltip(false)}
            className="hidden sm:flex items-center justify-center w-4 h-4 rounded-full text-gray-700 hover:text-cyan-400/70 transition-colors ml-0.5 shrink-0"
            aria-label="查看详细说明"
          >
            <HelpCircle size={11} />
          </button>
        </div>
      </div>

      {/* Fixed-position tooltip — escapes overflow-hidden parent */}
      {showTooltip && (
        <div
          style={{
            position: "fixed",
            top: tipPos.y,
            left: tipPos.x,
            zIndex: 1000,
            animation: "slide-up-fade 0.15s ease both",
          }}
          className="w-80 p-4 bg-gray-900 border border-gray-700/60 rounded-xl shadow-2xl pointer-events-none"
        >
          {/* arrow */}
          <div className="absolute -top-[5px] left-3 w-2.5 h-2.5 bg-gray-900 border-l border-t border-gray-700/60 rotate-45" />

          <div className="flex items-center gap-2 mb-2.5">
            <div className="w-5 h-5 rounded-md bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center shrink-0">
              <Icon size={10} className="text-cyan-400" />
            </div>
            <span className="text-xs font-semibold text-cyan-400">{title}</span>
          </div>
          <p className="text-xs text-gray-300 leading-relaxed">{detail}</p>
        </div>
      )}
    </>
  );
}
