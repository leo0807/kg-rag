"use client";

import { ChevronDown, ChevronLeft, ChevronRight, Settings } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useFavorites } from "@/app/favorites/useFavorites";
import { SidebarFooter } from "@/app/sidebar/SidebarFooter";
import { SidebarLink } from "@/app/sidebar/SidebarLink";
import {
  adminGroups,
  superAdminItem,
  tier1Items,
  tier2Groups,
  type SidebarGroup,
  type SidebarItem,
} from "@/app/sidebar/sidebarItems";
import { useCurrentUser } from "@/app/sidebar/useCurrentUser";

const SIDEBAR_KEY = "sidebar_collapsed";
const TIER2_OPEN = new Set(["analysis", "dev"]);

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [openGroups, setOpenGroups] = useState<Set<string>>(TIER2_OPEN);
  const { favorites } = useFavorites();
  const user = useCurrentUser();

  const allItems: SidebarItem[] = [
    ...tier1Items,
    ...tier2Groups.flatMap((g) => g.items),
    ...adminGroups.flatMap((g) => g.items),
    superAdminItem,
  ];

  useEffect(() => {
    if (localStorage.getItem(SIDEBAR_KEY) === "1") setCollapsed(true);
  }, []);

  function toggle() {
    setCollapsed((v) => {
      const next = !v;
      localStorage.setItem(SIDEBAR_KEY, next ? "1" : "0");
      return next;
    });
  }

  function toggleGroup(key: string) {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function isActive(href: string) {
    if (pathname === href) return true;
    if (pathname.startsWith(`${href}/`)) {
      const hasMoreSpecific = allItems.some(
        (item) =>
          item.href !== href &&
          item.href.length > href.length &&
          pathname.startsWith(item.href),
      );
      return !hasMoreSpecific;
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
      <div
        className="flex items-center justify-between px-3 py-4 min-h-[60px]"
        style={{ borderBottom: "1px solid var(--nav-border)" }}
      >
        {!collapsed && (
          <div>
            <div className="text-sm font-bold leading-tight" style={{ color: "var(--nav-text)" }}>
              商飞大模型
            </div>
            <div className="text-xs mt-0.5" style={{ color: "var(--nav-text-muted)" }}>
              航空工艺规范
            </div>
          </div>
        )}
        <button
          type="button"
          onClick={toggle}
          className={`p-1.5 rounded-lg hover:bg-white/10 transition-colors flex-shrink-0 ${collapsed ? "mx-auto" : "ml-auto"}`}
          style={{ color: "var(--nav-text-muted)" }}
          title={collapsed ? "展开菜单" : "折叠菜单"}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      <div className="md:hidden px-2 py-2 border-b" style={{ borderColor: "var(--nav-border)" }}>
        <SidebarLink href="/settings" label="设置" Icon={Settings} active={isActive("/settings")} collapsed={false} />
      </div>

      <nav className="flex-1 min-h-0 overflow-y-auto px-2 py-3 space-y-0.5">
        {/* Tier 1 — 常驻 */}
        <div className="space-y-0.5 pb-1">
          {tier1Items.map(({ href, label, shortcut, Icon }) => (
            <SidebarLink
              key={href}
              href={href}
              label={label}
              shortcut={shortcut}
              Icon={Icon}
              active={isActive(href)}
              badge={href === "/favorites" && favorites.length > 0 ? favorites.length : 0}
              collapsed={collapsed}
            />
          ))}
        </div>

        {/* Tier 2 — 分析 / 开发（accordion 展开 / rail flyout） */}
        {tier2Groups.map((group) => (
          <NavSubGroup
            key={group.key}
            group={group}
            open={openGroups.has(group.key)}
            collapsed={collapsed}
            onToggle={() => toggleGroup(group.key)}
            isActive={isActive}
          />
        ))}

        {/* Admin — 仅 is_admin，5 子组默认折叠 */}
        {user?.is_admin && (
          <div className="mt-1 pt-1 border-t" style={{ borderColor: "var(--nav-border)" }}>
            {adminGroups.map((group) => (
              <NavSubGroup
                key={group.key}
                group={group}
                open={openGroups.has(group.key)}
                collapsed={collapsed}
                onToggle={() => toggleGroup(group.key)}
                isActive={isActive}
              />
            ))}
            <SidebarLink
              href={superAdminItem.href}
              label={superAdminItem.label}
              Icon={superAdminItem.Icon}
              active={isActive(superAdminItem.href)}
              collapsed={collapsed}
            />
          </div>
        )}
      </nav>

      <SidebarFooter collapsed={collapsed} user={user} onLogout={handleLogout} />
    </aside>
  );
}

function NavSubGroup({
  group, open, collapsed, onToggle, isActive,
}: {
  group: SidebarGroup;
  open: boolean;
  collapsed: boolean;
  onToggle: () => void;
  isActive: (href: string) => boolean;
}) {
  const { label, Icon: GroupIcon, items } = group;

  if (collapsed) {
    // Rail mode: one group-icon button; hover triggers flyout panel
    return (
      <div className="relative group/flyout py-0.5">
        <div
          className="flex items-center justify-center py-2 rounded-lg cursor-default"
          style={{ color: "var(--nav-text-muted)" }}
          title={label}
        >
          <GroupIcon size={15} />
        </div>
        {/* Flyout panel */}
        <div
          className="absolute left-full top-0 ml-1 z-50 hidden group-hover/flyout:flex flex-col min-w-[160px] rounded-lg border py-1 shadow-xl"
          style={{ background: "var(--nav-bg)", borderColor: "var(--nav-border)" }}
        >
          <span
            className="px-3 py-1.5 text-[10px] uppercase tracking-wider select-none"
            style={{ color: "var(--nav-text-muted)" }}
          >
            {label}
          </span>
          {items.map(({ href, label: itemLabel, Icon }) => (
            <SidebarLink
              key={href}
              href={href}
              label={itemLabel}
              Icon={Icon}
              active={isActive(href)}
              collapsed={false}
            />
          ))}
        </div>
      </div>
    );
  }

  // Expanded mode: accordion
  return (
    <div className="space-y-0.5 pb-1">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between rounded-md px-3 py-1 text-[10px] uppercase tracking-wider transition-colors hover:bg-white/5"
        style={{ color: "var(--nav-text-muted)" }}
      >
        <span>{label}</span>
        <ChevronDown size={12} className={`transition-transform ${open ? "" : "-rotate-90"}`} />
      </button>
      {open && (
        <div className="space-y-0.5">
          {items.map(({ href, label: itemLabel, Icon }) => (
            <SidebarLink
              key={href}
              href={href}
              label={itemLabel}
              Icon={Icon}
              active={isActive(href)}
              collapsed={false}
            />
          ))}
        </div>
      )}
    </div>
  );
}
