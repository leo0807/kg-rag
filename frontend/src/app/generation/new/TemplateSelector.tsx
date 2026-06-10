"use client";

import { fetchApi } from "@/lib/api";
import { useEffect, useState } from "react";
import type { SpecTemplate } from "../types";

interface Props {
  value: string;
  onChange: (templateId: string, specType: string) => void;
}

export function TemplateSelector({ value, onChange }: Props) {
  const [templates, setTemplates] = useState<SpecTemplate[]>([]);
  const [loading, setLoading]     = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchApi<{ items: SpecTemplate[] }>("/api/admin/spec-templates")
      .then(d => setTemplates(d.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-xs text-gray-500 py-4">加载模板中…</div>;

  return (
    <div className="space-y-2">
      {templates.length === 0 && (
        <p className="text-xs text-gray-500">
          暂无模板。
          <a href="/admin/spec-templates" className="text-indigo-400 underline ml-1">
            去管理员页面初始化默认模板
          </a>
        </p>
      )}
      {templates.map(tpl => (
        <button
          key={tpl.id}
          type="button"
          onClick={() => onChange(tpl.template_id, tpl.applicable_to[0] ?? "")}
          className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
            value === tpl.template_id
              ? "border-indigo-600 bg-indigo-900/20 text-gray-100"
              : "border-gray-800 bg-gray-900 text-gray-400 hover:border-gray-700"
          }`}
        >
          <div className="text-sm font-medium">{tpl.name}</div>
          <div className="text-[10px] text-gray-500 mt-0.5">
            适用：{tpl.applicable_to.join("、")}
          </div>
          <div className="text-[10px] text-gray-600 mt-1">
            {(tpl.structure?.sections?.length ?? 0)} 个章节
          </div>
        </button>
      ))}
    </div>
  );
}
