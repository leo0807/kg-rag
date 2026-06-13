"use client";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

type Settings = {
  brand: { logo_url?: string; primary_color?: string; app_title?: string };
  notifications: { email_enabled?: boolean; quota_alert_pct?: number };
  advanced: { default_strategy?: string; default_language?: string; default_timezone?: string; custom_domain?: string };
  plan: string;
};

const INPUT = "w-full bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500";

export default function TenantSettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    fetchApi<Settings>("/api/admin/tenant-settings").then(setSettings).catch(() => {});
  }, []);

  const save = async () => {
    if (!settings) return;
    setSaving(true);
    setMsg("");
    try {
      await fetchApi("/api/admin/tenant-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brand: settings.brand, notifications: settings.notifications, advanced: settings.advanced }),
      });
      setMsg("✓ 保存成功");
    } catch {
      setMsg("保存失败");
    } finally {
      setSaving(false);
    }
  };

  const setBrand = (k: string, v: string) =>
    setSettings((s) => s ? { ...s, brand: { ...s.brand, [k]: v } } : s);
  const setAdv = (k: string, v: string) =>
    setSettings((s) => s ? { ...s, advanced: { ...s.advanced, [k]: v } } : s);
  const setNotif = (k: string, v: boolean | number) =>
    setSettings((s) => s ? { ...s, notifications: { ...s.notifications, [k]: v } } : s);

  if (!settings) return <div className="p-8 text-gray-400">加载中…</div>;

  const isEnterprise = settings.plan === "enterprise";

  return (
    <div className="p-6 max-w-2xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">租户设置</h1>
        <p className="text-gray-400 text-sm mt-1">当前套餐：<span className="text-blue-400">{settings.plan}</span></p>
      </div>

      <Section title="品牌设置">
        <Field label="应用标题">
          <input className={INPUT} value={settings.brand.app_title ?? ""} onChange={(e) => setBrand("app_title", e.target.value)} placeholder="CPS 知识库" />
        </Field>
        <Field label="Logo URL">
          <input className={INPUT} value={settings.brand.logo_url ?? ""} onChange={(e) => setBrand("logo_url", e.target.value)} placeholder="https://..." />
        </Field>
        <Field label="主色调">
          <div className="flex gap-2">
            <input type="color" value={settings.brand.primary_color ?? "#3b82f6"} onChange={(e) => setBrand("primary_color", e.target.value)} className="h-8 w-14 rounded border-0 bg-transparent" />
            <input className={`${INPUT} flex-1`} value={settings.brand.primary_color ?? "#3b82f6"} onChange={(e) => setBrand("primary_color", e.target.value)} />
          </div>
        </Field>
      </Section>

      <Section title="通知设置">
        <label className="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" checked={settings.notifications.email_enabled ?? true}
            onChange={(e) => setNotif("email_enabled", e.target.checked)}
            className="w-4 h-4 accent-blue-500" />
          <span className="text-sm text-gray-300">启用邮件通知</span>
        </label>
        <Field label="配额告警阈值 (%)">
          <input type="number" min={50} max={100} className={INPUT}
            value={settings.notifications.quota_alert_pct ?? 80}
            onChange={(e) => setNotif("quota_alert_pct", parseInt(e.target.value))} />
        </Field>
      </Section>

      <Section title={`高级设置${!isEnterprise ? " （企业版专属功能已锁定）" : ""}`}>
        <Field label="默认检索策略">
          <select className={INPUT} value={settings.advanced.default_strategy ?? "parallel"} onChange={(e) => setAdv("default_strategy", e.target.value)}>
            <option value="parallel">parallel</option>
            <option value="sequential">sequential</option>
          </select>
        </Field>
        <Field label="默认时区">
          <input className={INPUT} value={settings.advanced.default_timezone ?? "Asia/Shanghai"} onChange={(e) => setAdv("default_timezone", e.target.value)} />
        </Field>
        {isEnterprise && (
          <Field label="自定义域名">
            <input className={INPUT} value={settings.advanced.custom_domain ?? ""} onChange={(e) => setAdv("custom_domain", e.target.value)} placeholder="acme.kgrag.com" />
          </Field>
        )}
      </Section>

      <div className="flex items-center gap-4">
        <button onClick={save} disabled={saving}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded text-sm">
          {saving ? "保存中…" : "保存设置"}
        </button>
        {msg && <span className={`text-sm ${msg.startsWith("✓") ? "text-green-400" : "text-red-400"}`}>{msg}</span>}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-gray-800 rounded-lg p-5 space-y-4">
      <h2 className="text-white font-medium text-sm border-b border-gray-700 pb-2">{title}</h2>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      {children}
    </div>
  );
}
