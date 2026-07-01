"use client";

import type { ModelSettings } from "./types";

export interface Field {
  key: keyof ModelSettings;
  label: string;
  placeholder?: string;
  type?: "text" | "password";
}

export function SectionCard({ title, desc, children }: {
  title: string; desc: string; children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-gray-800 bg-gray-950/90 p-4 sm:p-5">
      <div className="mb-4">
        <div className="text-sm font-semibold text-white">{title}</div>
        <div className="mt-1 text-xs leading-5 text-gray-500">{desc}</div>
      </div>
      {children}
    </section>
  );
}

export function ModeSwitch({ value, options, onChange }: {
  value: string;
  options: { label: string; value: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <button type="button" key={opt.value} onClick={() => onChange(opt.value)}
          className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
            value === opt.value
              ? "border-amber-400/70 bg-amber-500/15 text-white"
              : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
          }`}>
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export function FieldGrid({ settings, fields, onChange }: {
  settings: ModelSettings;
  fields: Field[];
  onChange: (key: keyof ModelSettings, value: string) => void;
}) {
  const INPUT = "w-full rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none transition-colors focus:border-amber-400/70";
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {fields.map((field) => (
        <div key={field.key}>
          <label htmlFor={String(field.key)} className="mb-1 block text-xs text-gray-500">
            {field.label}
          </label>
          <input id={String(field.key)} type={field.type ?? "text"}
            value={settings[field.key]} placeholder={field.placeholder}
            onChange={(e) => onChange(field.key, e.target.value)}
            className={INPUT} />
        </div>
      ))}
    </div>
  );
}
