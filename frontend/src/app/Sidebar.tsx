"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useFavorites } from "@/app/favorites/useFavorites";
import { SidebarFooter } from "@/app/sidebar/SidebarFooter";
import { SidebarLink } from "@/app/sidebar/SidebarLink";
import { adminNavItems, mainNavItems } from "@/app/sidebar/sidebarItems";
import { useCurrentUser } from "@/app/sidebar/useCurrentUser";

const STORAGE_KEY = "sidebar_collapsed";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const { favorites } = useFavorites();
  const user = useCurrentUser();
  const allNavItems = [...mainNavItems, ...adminNavItems];

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === "1") setCollapsed(true);
  }, []);

  function toggle() {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  function isActive(href: string) {
    if (pathname === href) return true;
    // 如果当前路径以某个 href 开头，我们需要检查是否有更精确（更长）的匹配项在导航栏中
    if (pathname.startsWith(`${href}/`)) {
      const hasMoreSpecificMatch = allNavItems.some(
        (item) =>
          item.href !== href &&
          item.href.length > href.length &&
          pathname.startsWith(item.href),
      );
      return !hasMoreSpecificMatch;
    }
    return false;
  }

  function handleLogout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  }

  return (
    <aside
      className={`flex-shrink-0 border-r flex flex-col transition-all duration-200 ${collapsed ? "w-14" : "w-44"}`}
      style={{ background: "var(--nav-bg)", borderColor: "var(--nav-border)" }}
    >
      {/* Logo + 折叠按钮 */}
      <div
        className="flex items-center justify-between px-3 py-4 min-h-[60px]"
        style={{ borderBottom: "1px solid var(--nav-border)" }}
      >
        {!collapsed && (
          <div>
            <div
              className="text-sm font-bold leading-tight"
              style={{ color: "var(--nav-text)" }}
            >
              商飞大模型
            </div>
            <div
              className="text-xs mt-0.5"
              style={{ color: "var(--nav-text-muted)" }}
            >
              航空工艺规范
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={toggle}
          className={`p-1.5 rounded-lg hover:bg-white/10
                                transition-colors flex-shrink-0 ${collapsed ? "mx-auto" : "ml-auto"}`}
          style={{ color: "var(--nav-text-muted)" }}
          title={collapsed ? "展开菜单" : "折叠菜单"}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      {/* 导航（可滚动，flex-1 撑满剩余空间） */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
        {mainNavItems.map(({ href, label, shortcut, Icon }) => {
          const active = isActive(href);
          const badge =
            href === "/favorites" && favorites.length > 0
              ? favorites.length
              : 0;
          return (
            <SidebarLink
              key={href}
              href={href}
              label={label}
              shortcut={shortcut}
              Icon={Icon}
              active={active}
              badge={badge}
              collapsed={collapsed}
            />
          );
        })}
      </nav>

      {/* 管理员专属：用量监控（固定在可滚动区之外） */}
      {user?.is_admin && (
        <div className="flex-shrink-0 px-2 pb-1">
          {!collapsed && (
            <div
              className="text-[10px] uppercase tracking-wider px-3 py-1"
              style={{ color: "var(--nav-text-muted)" }}
            >
              Admin
            </div>
          )}
          {adminNavItems.map(({ href, label, Icon }) => (
            <SidebarLink
              key={href}
              href={href}
              label={label}
              Icon={Icon}
              active={isActive(href)}
              collapsed={collapsed}
            />
          ))}
        </div>
      )}

      <SidebarFooter
        collapsed={collapsed}
        user={user}
        onLogout={handleLogout}
      />
    </aside>
  );
}
