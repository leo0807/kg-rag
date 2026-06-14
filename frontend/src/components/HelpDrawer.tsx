"use client";

import { useEffect, useRef, useState } from "react";
import { CircleHelp, ChevronRight, X } from "lucide-react";
import { usePathname } from "next/navigation";
import { findGuide } from "@/lib/page-guides";

// SSR-safe localStorage helpers — 仅在 useEffect 内调用，但加守卫以防万一
const PULSE_KEY = "help_pulsed_v1";

function getPulsedSet(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    return new Set<string>(
      JSON.parse(localStorage.getItem(PULSE_KEY) ?? "[]") as string[]
    );
  } catch {
    return new Set();
  }
}

function markPulsed(key: string): void {
  if (typeof window === "undefined") return;
  const set = getPulsedSet();
  set.add(key);
  localStorage.setItem(PULSE_KEY, JSON.stringify([...set]));
}

export default function HelpDrawer() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [pulsing, setPulsing] = useState(false);

  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  const result = findGuide(pathname);
  const guide = result?.guide ?? null;
  const patternKey = result?.key ?? pathname;

  // 路由变化时关闭抽屉，并检查是否需要显示脉冲提示
  useEffect(() => {
    setOpen(false);
    if (!guide) return;
    // SSR-safe：在 useEffect 中读取 localStorage
    const pulsed = getPulsedSet();
    setPulsing(!pulsed.has(patternKey));
  }, [patternKey, guide]);

  // ESC 关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  // 打开时聚焦关闭按钮
  useEffect(() => {
    if (open) {
      // 等待 transition 开始后再聚焦，避免 translate 动画中 focus 丢失
      const t = setTimeout(() => closeRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [open]);

  // 移动端锁定 body 滚动（桌面端不锁，侧边栏仍可用）
  useEffect(() => {
    if (typeof window === "undefined") return;
    const isMobile = window.innerWidth < 768;
    if (open && isMobile) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const handleOpen = () => {
    setOpen(true);
    setPulsing(false);
    markPulsed(patternKey);
  };

  const handleClose = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  // 当前页面无帮助内容时不渲染任何东西（如 /login）
  if (!guide) return null;

  return (
    <>
      {/* ── 触发按钮（右下角固定浮动）────────────────────────────── */}
      <button
        ref={triggerRef}
        onClick={handleOpen}
        aria-label="打开页面帮助"
        aria-expanded={open}
        aria-controls="help-drawer"
        className={[
          "fixed bottom-20 right-4 z-[35]",
          "w-9 h-9 flex items-center justify-center rounded-full",
          "bg-gray-800 border border-gray-700 text-gray-400",
          "hover:text-white hover:bg-gray-700 hover:border-gray-500",
          "transition-colors shadow-lg",
          pulsing ? "animate-pulse" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <CircleHelp size={16} />
      </button>

      {/* ── 移动端遮罩（桌面端不显示，不阻塞侧边栏）─────────────── */}
      {open && (
        <div
          className="fixed inset-0 z-[39] bg-black/50 md:hidden"
          aria-hidden="true"
          onClick={handleClose}
        />
      )}

      {/* ── 帮助抽屉 ─────────────────────────────────────────────── */}
      <aside
        id="help-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="页面帮助"
        className={[
          "fixed inset-y-0 right-0 z-40",
          "w-full md:w-80",
          "bg-gray-900 border-l border-gray-800 shadow-2xl",
          "flex flex-col overflow-hidden",
          "transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "translate-x-full",
        ].join(" ")}
      >
        {/* 标题栏 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800 shrink-0">
          <div className="flex items-center gap-2">
            <CircleHelp size={14} className="text-indigo-400 shrink-0" />
            <span className="text-white text-sm font-medium">{guide.title}</span>
          </div>
          <button
            ref={closeRef}
            onClick={handleClose}
            aria-label="关闭帮助面板"
            className="p-1 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        {/* 内容区（可滚动）*/}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5 text-sm">
          {/* 一句话简介 */}
          <p className="text-gray-300 leading-relaxed">{guide.summary}</p>

          {/* 主要功能 */}
          {guide.features.length > 0 && (
            <section>
              <h3 className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                主要功能
              </h3>
              <ul className="space-y-1.5">
                {guide.features.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-gray-300">
                    <span className="text-indigo-400 shrink-0 mt-0.5 leading-5">•</span>
                    <span className="leading-5">{f}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* 常见操作 */}
          {guide.actions.length > 0 && (
            <section>
              <h3 className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                常见操作
              </h3>
              <ol className="space-y-1.5">
                {guide.actions.map((a, i) => (
                  <li key={i} className="flex items-start gap-2 text-gray-300">
                    <span className="text-gray-600 shrink-0 tabular-nums leading-5 w-4">
                      {i + 1}.
                    </span>
                    <span className="leading-5">{a}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {/* 相关页面 */}
          {guide.related.length > 0 && (
            <section>
              <h3 className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                相关页面
              </h3>
              <div className="space-y-1">
                {guide.related.map((r) => (
                  <a
                    key={r.href}
                    href={r.href}
                    onClick={handleClose}
                    className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors group"
                  >
                    <span>{r.label}</span>
                    <ChevronRight
                      size={13}
                      className="text-gray-600 group-hover:text-gray-400 shrink-0"
                    />
                  </a>
                ))}
              </div>
            </section>
          )}
        </div>
      </aside>
    </>
  );
}
