"use client";

import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Settings,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { type Dispatch, type SetStateAction, useEffect, useState } from "react";
import { useFavorites } from "@/app/favorites/useFavorites";
import { SidebarFooter } from "@/app/sidebar/SidebarFooter";
import { SidebarLink } from "@/app/sidebar/SidebarLink";
import { adminNavItems, mainNavItems } from "@/app/sidebar/sidebarItems";
import { useCurrentUser } from "@/app/sidebar/useCurrentUser";

const STORAGE_KEY = "sidebar_collapsed";
const MAIN_SECTION_KEY = "sidebar_main_section_collapsed";
const ADMIN_SECTION_KEY = "sidebar_admin_section_collapsed";

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mainSectionCollapsed, setMainSectionCollapsed] = useState(false);
  const [adminSectionCollapsed, setAdminSectionCollapsed] = useState(false);
  const { favorites } = useFavorites();
  const user = useCurrentUser();
  const allNavItems = [...mainNavItems, ...adminNavItems];

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === "1") setCollapsed(true);
    if (localStorage.getItem(MAIN_SECTION_KEY) === "1")
      setMainSectionCollapsed(true);
    if (localStorage.getItem(ADMIN_SECTION_KEY) === "1")
      setAdminSectionCollapsed(true);
  }, []);

  function toggle() {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  }

  function toggleSection(
    key: string,
    setter: Dispatch<SetStateAction<boolean>>,
  ) {
    setter((v) => {
      const next = !v;
      localStorage.setItem(key, next ? "1" : "0");
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
      className={`flex-shrink-0 border-r flex flex-col transition-all duration-200 h-full min-h-0 ${collapsed ? "w-14" : "w-44"}`}
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

      <div
        className="md:hidden px-2 py-2 border-b"
        style={{ borderColor: "var(--nav-border)" }}
      >
        <SidebarLink
          href="/settings"
          label="设置"
          Icon={Settings}
          active={isActive("/settings")}
          collapsed={false}
        />
      </div>

      {/* 导航（可滚动，flex-1 撑满剩余空间） */}
      <nav className="flex-1 min-h-0 overflow-y-auto px-2 py-3 space-y-0.5">
        <NavSection
          title="常用功能"
          collapsed={collapsed}
          sectionCollapsed={mainSectionCollapsed}
          onToggle={() =>
            toggleSection(MAIN_SECTION_KEY, setMainSectionCollapsed)
          }
        >
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
        </NavSection>

        {user?.is_admin && (
          <NavSection
            title="Admin"
            collapsed={collapsed}
            sectionCollapsed={adminSectionCollapsed}
            onToggle={() =>
              toggleSection(ADMIN_SECTION_KEY, setAdminSectionCollapsed)
            }
          >
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
          </NavSection>
        )}
      </nav>

      <SidebarFooter
        collapsed={collapsed}
        user={user}
        onLogout={handleLogout}
      />
    </aside>
  );
}

function NavSection({
  title,
  collapsed,
  sectionCollapsed,
  onToggle,
  children,
}: {
  title: string;
  collapsed: boolean;
  sectionCollapsed: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  if (collapsed) {
    return <div className="space-y-0.5">{children}</div>;
  }

  return (
    <div className="space-y-1 pb-2">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between rounded-md px-3 py-1 text-[10px] uppercase tracking-wider transition-colors hover:bg-white/5"
        style={{ color: "var(--nav-text-muted)" }}
      >
        <span>{title}</span>
        <ChevronDown
          size={12}
          className={`transition-transform ${sectionCollapsed ? "-rotate-90" : ""}`}
        />
      </button>
      {!sectionCollapsed && <div className="space-y-0.5">{children}</div>}
    </div>
  );
}
