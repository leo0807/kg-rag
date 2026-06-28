"use client";

import Link from "next/link";
import type { SidebarItem } from "./sidebarItems";

interface Props extends SidebarItem {
  active: boolean;
  badge?: number;
  collapsed: boolean;
}

export function SidebarLink({
  href,
  label,
  shortcut,
  Icon,
  active,
  badge = 0,
  collapsed,
}: Props) {
  return (
    <Link
      href={href}
      title={
        collapsed ? `${label}${shortcut ? `  ${shortcut}` : ""}` : undefined
      }
      className={`flex items-center gap-2.5 rounded-lg text-sm transition-all duration-200 group
        ${collapsed ? "justify-center px-0 py-2.5" : "px-3 py-2"}
        ${
          active
            ? "bg-[var(--nav-active-bg)] text-[var(--nav-text)] border-l-2 border-cyan-400/80 shadow-[inset_0_0_16px_rgba(34,211,238,0.07)]"
            : "text-[var(--nav-text-muted)] hover:text-[var(--nav-text)] hover:bg-white/10 border-l-2 border-transparent"
        }`}
    >
      <div className={`relative flex-shrink-0 transition-all duration-200 ${active ? "drop-shadow-[0_0_4px_rgba(34,211,238,0.7)]" : "group-hover:opacity-90"}`}>
        <Icon size={15} />
        {badge > 0 && collapsed && (
          <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-amber-500 rounded-full flex items-center justify-center text-[8px] text-white font-bold">
            {badge > 9 ? "9+" : badge}
          </span>
        )}
      </div>
      {!collapsed && (
        <>
          <span className="flex-1">{label}</span>
          {badge > 0 && (
            <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 text-[10px] font-bold rounded-full">
              {badge}
            </span>
          )}
          {shortcut && badge === 0 && (
            <span
              className="text-xs font-mono"
              style={{
                color: active
                  ? "rgba(255,255,255,0.6)"
                  : "var(--nav-text-muted)",
              }}
            >
              {shortcut}
            </span>
          )}
        </>
      )}
    </Link>
  );
}
