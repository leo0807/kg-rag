"use client";

import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

interface Prefs {
  theme: string;
  language: string;
  default_strategy: string;
  show_sources: boolean;
  show_metrics: boolean;
  answer_style: string;
  ui_density: string;
}

const STRATEGY_OPTS = [
  { value: "parallel", label: "并行检索（默认）" },
  { value: "graph", label: "图谱优先" },
  { value: "vector", label: "向量检索" },
  { value: "hybrid", label: "混合策略" },
];

const STYLE_OPTS = [
  { value: "professional", label: "专业" },
  { value: "concise", label: "简洁" },
  { value: "detailed", label: "详细" },
];

const DENSITY_OPTS = [
  { value: "comfortable", label: "舒适" },
  { value: "compact", label: "紧凑" },
];

interface Props {
  showMsg: (m: string) => void;
  showError: (e: string) => void;
}

export function PreferencesTab({ showMsg, showError }: Props) {
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchApi<Prefs>("/api/preferences").then(setPrefs).catch(() => {});
  }, []);

  async function save() {
    if (!prefs) return;
    setSaving(true);
    try {
      await fetchApi("/api/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(prefs),
      });
      showMsg("偏好已保存");
    } catch {
      showError("保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (!prefs) return <p className="text-xs text-gray-600 py-8 text-center">加载中…</p>;

  return (
    <div className="space-y-6">
      <Field label="默认检索策略">
        <Select value={prefs.default_strategy}
          onChange={(v) => setPrefs({ ...prefs, default_strategy: v })}
          options={STRATEGY_OPTS} />
      </Field>

      <Field label="回答风格">
        <Select value={prefs.answer_style}
          onChange={(v) => setPrefs({ ...prefs, answer_style: v })}
          options={STYLE_OPTS} />
      </Field>

      <Field label="界面密度">
        <Select value={prefs.ui_density}
          onChange={(v) => setPrefs({ ...prefs, ui_density: v })}
          options={DENSITY_OPTS} />
      </Field>

      <Field label="显示来源">
        <Toggle checked={prefs.show_sources}
          onChange={(v) => setPrefs({ ...prefs, show_sources: v })} />
      </Field>

      <Field label="显示性能指标">
        <Toggle checked={prefs.show_metrics}
          onChange={(v) => setPrefs({ ...prefs, show_metrics: v })} />
      </Field>

      <div className="pt-2">
        <button onClick={save} disabled={saving}
          className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm
                     rounded-lg transition-colors disabled:opacity-50">
          {saving ? "保存中…" : "保存偏好"}
        </button>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-gray-300">{label}</span>
      {children}
    </div>
  );
}

function Select({ value, onChange, options }: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      className="bg-gray-900 border border-gray-700 text-sm text-gray-200
                 rounded-lg px-3 py-1.5 outline-none focus:border-indigo-600">
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button type="button" onClick={() => onChange(!checked)}
      className={`w-10 h-5 rounded-full transition-colors relative ${
        checked ? "bg-indigo-600" : "bg-gray-700"
      }`}>
      <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${
        checked ? "left-5" : "left-0.5"
      }`} />
    </button>
  );
}
