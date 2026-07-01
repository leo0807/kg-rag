"use client";

import { ChevronDown } from "lucide-react";
import type { SidebarGroup } from "./sidebarItems";
import { SidebarLink } from "./SidebarLink";

interface Props {
  group:    SidebarGroup;
  open:     boolean;
  collapsed: boolean;
  onToggle: () => void;
  isActive: (href: string) => boolean;
}

export function NavSubGroup({ group, open, collapsed, onToggle, isActive }: Props) {
  const { label, Icon: GroupIcon, items } = group;

  if (collapsed) {
    return (
      <div className="relative group/flyout py-0.5">
        <div className="flex items-center justify-center py-2 rounded-lg cursor-default"
          style={{ color: "var(--nav-text-muted)" }} title={label}>
          <GroupIcon size={15} />
        </div>
        <div className="absolute left-full top-0 ml-1 z-50 hidden group-hover/flyout:flex flex-col min-w-[160px] rounded-lg border py-1 shadow-xl"
          style={{ background: "var(--nav-bg)", borderColor: "var(--nav-border)" }}>
          <span className="px-3 py-1.5 text-[10px] uppercase tracking-wider select-none"
            style={{ color: "var(--nav-text-muted)" }}>
            {label}
          </span>
          {items.map(({ href, label: itemLabel, Icon }) => (
            <SidebarLink key={href} href={href} label={itemLabel} Icon={Icon}
              active={isActive(href)} collapsed={false} />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-0.5 pb-1">
      <button type="button" onClick={onToggle}
        className="flex w-full items-center justify-between rounded-md px-3 py-1 text-[10px] uppercase tracking-wider transition-colors hover:bg-white/5"
        style={{ color: "var(--nav-text-muted)" }}>
        <span>{label}</span>
        <ChevronDown size={12} className={`transition-transform ${open ? "" : "-rotate-90"}`} />
      </button>
      {open && (
        <div className="space-y-0.5">
          {items.map(({ href, label: itemLabel, Icon }) => (
            <SidebarLink key={href} href={href} label={itemLabel} Icon={Icon}
              active={isActive(href)} collapsed={false} />
          ))}
        </div>
      )}
    </div>
  );
}
