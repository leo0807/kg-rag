"use client";

import { LogOut } from "lucide-react";
import ThemeToggle from "@/components/ThemeToggle";
import type { CurrentUser } from "./useCurrentUser";

interface Props {
  collapsed: boolean;
  user: CurrentUser | null;
  onLogout: () => void;
}

export function SidebarFooter({ collapsed, user, onLogout }: Props) {
  return (
    <div
      className="flex-shrink-0"
      style={{ borderTop: "1px solid var(--nav-border)" }}
    >
      {!collapsed && (
        <div
          className="flex-shrink-0 px-4 py-2"
          style={{ borderTop: "1px solid var(--nav-border)" }}
        >
          <div
            className="text-xs space-y-0.5"
            style={{ color: "var(--nav-text-muted)" }}
          >
            <div className="flex justify-between">
              <span>搜索</span>
              <span className="font-mono">⌘K</span>
            </div>
            <div className="flex justify-between">
              <span>问答</span>
              <span className="font-mono">⌘/</span>
            </div>
          </div>
        </div>
      )}

      {!collapsed && user && (
        <div
          className="px-4 py-3"
          style={{ borderBottom: "1px solid var(--nav-border)" }}
        >
          <div
            className="text-xs font-medium truncate"
            style={{ color: "var(--nav-text)" }}
          >
            {user.full_name || user.username}
          </div>
          <div
            className="text-xs mt-0.5 truncate"
            style={{ color: "var(--nav-text-muted)" }}
          >
            {user.department}
          </div>
        </div>
      )}

      <div
        className={`py-3 flex items-center gap-2 ${collapsed ? "flex-col justify-center px-0" : "px-4 justify-between"}`}
      >
        {!collapsed && (
          <div className="text-xs" style={{ color: "var(--nav-text-muted)" }}>
            v1.1.0
          </div>
        )}
        <ThemeToggle />
        <button
          type="button"
          onClick={onLogout}
          className="p-1.5 rounded-lg hover:text-red-400 hover:bg-white/10 transition-colors"
          style={{ color: "var(--nav-text-muted)" }}
          title="退出登录"
        >
          <LogOut size={15} />
        </button>
      </div>
    </div>
  );
}
