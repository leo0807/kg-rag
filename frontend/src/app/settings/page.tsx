"use client";

import { useEffect, useState } from "react";
import { User, KeyRound, Cpu, Sliders, Users, ClipboardList, Search, Filter, Bell } from "lucide-react";
import { AdminTab } from "./AdminTab";
import { AlertTab } from "./AlertTab";
import { AuditTab } from "./AuditTab";
import { EntityFilterTab } from "./EntityFilterTab";
import { ModelTab } from "./ModelTab";
import { PasswordTab } from "./PasswordTab";
import { PreferencesTab } from "./PreferencesTab";
import { ProfileTab } from "./ProfileTab";
import { SearchTab } from "./SearchTab";
import type { Tab } from "./types";

const BASE_TABS: { key: Tab; label: string; desc: string; Icon: React.ElementType; group: "user" | "admin" }[] = [
  { key: "profile",     label: "个人资料", desc: "姓名、部门与邮箱",       Icon: User,          group: "user" },
  { key: "password",    label: "修改密码", desc: "更新登录凭证",           Icon: KeyRound,      group: "user" },
  { key: "model",       label: "模型设置", desc: "LLM / Embedding 参数", Icon: Cpu,           group: "user" },
  { key: "preferences", label: "使用偏好", desc: "检索策略与外观",         Icon: Sliders,       group: "user" },
];
const ADMIN_TABS: { key: Tab; label: string; desc: string; Icon: React.ElementType; group: "admin" }[] = [
  { key: "admin",         label: "用户管理", desc: "创建与管理系统用户",  Icon: Users,         group: "admin" },
  { key: "audit",         label: "审计日志", desc: "查看关键操作记录",    Icon: ClipboardList, group: "admin" },
  { key: "search",        label: "检索配置", desc: "混合检索 alpha 权重", Icon: Search,        group: "admin" },
  { key: "entity_filter", label: "实体过滤", desc: "黑白名单控制权重",    Icon: Filter,        group: "admin" },
  { key: "alert",         label: "告警推送", desc: "钉钉/企微 Webhook",  Icon: Bell,          group: "admin" },
];

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("profile");
  const [isAdmin, setIsAdmin] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      const u = JSON.parse(localStorage.getItem("user") || "{}");
      setIsAdmin(u.is_admin ?? false);
    } catch {}
  }, []);

  function showMsg(m: string)   { setMsg(m); setError(""); setTimeout(() => setMsg(""), 3000); }
  function showError(e: string) { setError(e); setMsg(""); setTimeout(() => setError(""), 3000); }

  const tabs = [...BASE_TABS, ...(isAdmin ? ADMIN_TABS : [])];
  const active = tabs.find(t => t.key === tab);

  return (
    <div className="px-4 py-4 sm:p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-white">设置</h1>
        <p className="text-sm text-gray-500 mt-0.5">管理账号信息、模型参数与系统配置</p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[220px_1fr]">
        {/* Sidebar nav */}
        <aside className="h-fit lg:sticky lg:top-4 space-y-1">
          {/* User section */}
          <div className="text-[10px] uppercase tracking-widest text-gray-600 px-3 pb-1.5">账号</div>
          {BASE_TABS.map(t => (
            <NavItem key={t.key} t={t} active={tab === t.key} onClick={() => setTab(t.key)} />
          ))}

          {/* Admin section */}
          {isAdmin && (
            <>
              <div className="text-[10px] uppercase tracking-widest text-gray-600 px-3 pb-1.5 pt-4">管理员</div>
              {ADMIN_TABS.map(t => (
                <NavItem key={t.key} t={t} active={tab === t.key} onClick={() => setTab(t.key)} />
              ))}
            </>
          )}
        </aside>

        {/* Content */}
        <section className="space-y-4 min-w-0">
          {/* Section header */}
          {active && (
            <div className="flex items-center gap-3 px-5 py-4 bg-gray-900 border border-gray-800 rounded-xl">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0">
                <active.Icon size={15} className="text-indigo-400" />
              </div>
              <div>
                <div className="text-sm font-semibold text-white">{active.label}</div>
                <div className="text-xs text-gray-500 mt-0.5">{active.desc}</div>
              </div>
            </div>
          )}

          {msg   && <div className="px-4 py-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-sm text-emerald-400">{msg}</div>}
          {error && <div className="px-4 py-2.5 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">{error}</div>}

          {tab === "profile"       && <ProfileTab     showMsg={showMsg} showError={showError} />}
          {tab === "password"      && <PasswordTab    showMsg={showMsg} showError={showError} />}
          {tab === "model"         && <ModelTab       showMsg={showMsg} showError={showError} />}
          {tab === "preferences"   && <PreferencesTab showMsg={showMsg} showError={showError} />}
          {tab === "admin"         && <AdminTab       showMsg={showMsg} showError={showError} />}
          {tab === "audit"         && <AuditTab />}
          {tab === "search"        && <SearchTab      showMsg={showMsg} showError={showError} />}
          {tab === "entity_filter" && <EntityFilterTab />}
          {tab === "alert"         && <AlertTab       showMsg={showMsg} showError={showError} />}
        </section>
      </div>
    </div>
  );
}

function NavItem({ t, active, onClick }: {
  t: { key: string; label: string; desc: string; Icon: React.ElementType };
  active: boolean; onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all ${
        active
          ? "bg-indigo-600/15 border border-indigo-500/30 shadow-[inset_0_0_20px_rgba(99,102,241,0.05)]"
          : "border border-transparent hover:bg-gray-900 hover:border-gray-800"
      }`}>
      <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
        active ? "bg-indigo-500/15 border border-indigo-500/25" : "bg-gray-800/80 border border-gray-700/50"
      }`}>
        <t.Icon size={13} className={active ? "text-indigo-400" : "text-gray-500"} />
      </div>
      <div className="min-w-0">
        <div className={`text-sm font-medium transition-colors ${active ? "text-white" : "text-gray-400"}`}>{t.label}</div>
        <div className="text-[11px] text-gray-600 mt-0.5 truncate">{t.desc}</div>
      </div>
    </button>
  );
}
