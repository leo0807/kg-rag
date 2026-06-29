"use client";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Palette, Bell, Settings2, Lock, Zap } from "lucide-react";

type Settings = {
  brand: { logo_url?: string; primary_color?: string; app_title?: string };
  notifications: { email_enabled?: boolean; quota_alert_pct?: number };
  advanced: { default_strategy?: string; default_language?: string; default_timezone?: string; custom_domain?: string };
  plan: string;
};

const TIMEZONES = [
  { v: "Asia/Shanghai",      l: "Asia/Shanghai (UTC+8)" },
  { v: "Asia/Hong_Kong",     l: "Asia/Hong_Kong (UTC+8)" },
  { v: "Asia/Tokyo",         l: "Asia/Tokyo (UTC+9)" },
  { v: "Asia/Singapore",     l: "Asia/Singapore (UTC+8)" },
  { v: "Asia/Seoul",         l: "Asia/Seoul (UTC+9)" },
  { v: "Europe/London",      l: "Europe/London (UTC+0)" },
  { v: "Europe/Paris",       l: "Europe/Paris (UTC+1)" },
  { v: "Europe/Berlin",      l: "Europe/Berlin (UTC+1)" },
  { v: "America/New_York",   l: "America/New_York (UTC-5)" },
  { v: "America/Los_Angeles",l: "America/Los_Angeles (UTC-8)" },
  { v: "UTC",                l: "UTC (UTC+0)" },
];

const STRATEGIES = [
  { v: "parallel",   l: "Parallel — 并行多路召回（推荐）" },
  { v: "sequential", l: "Sequential — 顺序策略链" },
  { v: "hybrid",     l: "Hybrid — 向量+关键词混合" },
];

const PLAN_FEATURES: Record<string, string[]> = {
  free:       ["单租户", "10k 节点", "5 并发", "社区支持"],
  standard:   ["单租户", "500k 节点", "20 并发", "邮件支持", "Webhook"],
  enterprise: ["多租户", "无限节点", "无限并发", "专属支持", "自定义域名", "SSO"],
};

const INPUT = "w-full bg-gray-800/60 border border-gray-700/60 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500/70 focus:bg-gray-800 transition-colors";

function Section({ icon: Icon, title, children }: { icon: React.ElementType; title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      <div className="flex items-center gap-2.5 pb-3 border-b border-gray-800">
        <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
          <Icon size={14} className="text-blue-400" />
        </div>
        <h2 className="text-white font-medium text-sm">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-gray-500 mb-1.5 font-medium">{label}</label>
      {children}
    </div>
  );
}

export default function TenantSettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetchApi<Settings>("/api/admin/tenant-settings").then(setSettings).catch(() => {});
  }, []);

  const save = async () => {
    if (!settings) return;
    setSaving(true); setMsg("");
    try {
      await fetchApi("/api/admin/tenant-settings", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brand: settings.brand, notifications: settings.notifications, advanced: settings.advanced }),
      });
      setMsg("✓ 保存成功");
    } catch { setMsg("保存失败"); } finally { setSaving(false); }
  };

  const setBrand = (k: string, v: string) =>
    setSettings(s => s ? { ...s, brand: { ...s.brand, [k]: v } } : s);
  const setAdv = (k: string, v: string) =>
    setSettings(s => s ? { ...s, advanced: { ...s.advanced, [k]: v } } : s);
  const setNotif = (k: string, v: boolean | number) =>
    setSettings(s => s ? { ...s, notifications: { ...s.notifications, [k]: v } } : s);

  if (!settings) return <div className="p-8 text-gray-400 text-sm">加载中…</div>;

  const isEnterprise = settings.plan === "enterprise";
  const planColor = settings.plan === "enterprise" ? "text-purple-400" : settings.plan === "standard" ? "text-blue-400" : "text-gray-400";

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">租户设置</h1>
          <p className="text-gray-500 text-sm mt-1">配置品牌、通知与高级功能</p>
        </div>
        <div className="flex items-center gap-3">
          {msg && <span className={`text-sm ${msg.startsWith("✓") ? "text-green-400" : "text-red-400"}`}>{msg}</span>}
          <button onClick={save} disabled={saving}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors">
            {saving ? "保存中…" : "保存设置"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
        {/* LEFT — main settings */}
        <div className="space-y-5">
          <Section icon={Palette} title="品牌设置">
            <div className="grid grid-cols-2 gap-4">
              <Field label="应用标题">
                <input className={INPUT} value={settings.brand.app_title ?? ""} onChange={e => setBrand("app_title", e.target.value)} placeholder="CPS 知识库" />
              </Field>
              <Field label="Logo URL">
                <input className={INPUT} value={settings.brand.logo_url ?? ""} onChange={e => setBrand("logo_url", e.target.value)} placeholder="https://..." />
              </Field>
              <Field label="主色调">
                <div className="flex gap-2">
                  <input type="color" value={settings.brand.primary_color ?? "#3b82f6"} onChange={e => setBrand("primary_color", e.target.value)}
                    className="h-9 w-12 rounded-lg border border-gray-700 bg-transparent cursor-pointer" />
                  <input className={`${INPUT} flex-1`} value={settings.brand.primary_color ?? "#3b82f6"} onChange={e => setBrand("primary_color", e.target.value)} />
                </div>
              </Field>
            </div>
          </Section>

          <Section icon={Settings2} title={`高级设置${!isEnterprise ? " — 部分功能仅企业版可用" : ""}`}>
            <div className="grid grid-cols-2 gap-4">
              <Field label="默认检索策略">
                <select className={INPUT} value={settings.advanced.default_strategy ?? "parallel"} onChange={e => setAdv("default_strategy", e.target.value)}>
                  {STRATEGIES.map(({ v, l }) => <option key={v} value={v}>{l}</option>)}
                </select>
              </Field>
              <Field label="默认时区">
                <select className={INPUT} value={settings.advanced.default_timezone ?? "Asia/Shanghai"} onChange={e => setAdv("default_timezone", e.target.value)}>
                  {TIMEZONES.map(({ v, l }) => <option key={v} value={v}>{l}</option>)}
                </select>
              </Field>
              {isEnterprise && (
                <Field label="自定义域名">
                  <input className={INPUT} value={settings.advanced.custom_domain ?? ""} onChange={e => setAdv("custom_domain", e.target.value)} placeholder="acme.kgrag.com" />
                </Field>
              )}
            </div>
          </Section>
        </div>

        {/* RIGHT — sidebar */}
        <div className="space-y-5">
          {/* Plan card */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-3">
              <Zap size={14} className="text-yellow-400" />
              <h3 className="text-sm font-medium text-white">当前套餐</h3>
            </div>
            <div className={`text-lg font-bold uppercase mb-3 ${planColor}`}>{settings.plan}</div>
            <div className="space-y-1.5">
              {(PLAN_FEATURES[settings.plan] ?? []).map(f => (
                <div key={f} className="flex items-center gap-2 text-xs text-gray-400">
                  <div className="w-1 h-1 rounded-full bg-blue-400/60" />
                  {f}
                </div>
              ))}
            </div>
            {!isEnterprise && (
              <div className="mt-4 pt-3 border-t border-gray-800">
                <p className="text-xs text-gray-600">升级至企业版可解锁自定义域名、SSO 等高级功能</p>
              </div>
            )}
          </div>

          {/* Notifications */}
          <Section icon={Bell} title="通知设置">
            <label className="flex items-center gap-3 cursor-pointer group">
              <div className={`relative w-9 h-5 rounded-full transition-colors ${settings.notifications.email_enabled ? "bg-blue-600" : "bg-gray-700"}`}
                   onClick={() => setNotif("email_enabled", !settings.notifications.email_enabled)}>
                <div className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${settings.notifications.email_enabled ? "translate-x-4" : ""}`} />
              </div>
              <span className="text-sm text-gray-300">启用邮件通知</span>
            </label>
            <Field label="配额告警阈值 (%)">
              <div className="flex items-center gap-3">
                <input type="range" min={50} max={100} step={5}
                  value={settings.notifications.quota_alert_pct ?? 80}
                  onChange={e => setNotif("quota_alert_pct", parseInt(e.target.value))}
                  className="flex-1 accent-blue-500" />
                <span className="text-sm font-mono text-blue-400 w-10 text-right">
                  {settings.notifications.quota_alert_pct ?? 80}%
                </span>
              </div>
            </Field>
          </Section>

          {/* Lock notice for non-enterprise */}
          {!isEnterprise && (
            <div className="bg-gray-900/50 border border-gray-800 border-dashed rounded-xl p-4 flex items-start gap-3">
              <Lock size={14} className="text-gray-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-xs text-gray-500 font-medium mb-1">企业版专属</p>
                <p className="text-[11px] text-gray-700">自定义域名、多租户、SSO 单点登录等功能</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
