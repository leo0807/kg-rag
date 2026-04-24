"use client";

import { Check, Copy, Download } from "lucide-react";
import { useState } from "react";

interface Props {
  title: string;
  description: string;
  fields: string[];
  sample: string;
  filename: string;
}

function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], {
    type: "text/plain;charset=utf-8",
  });
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(href);
}

export function TemplateCard({
  title,
  description,
  fields,
  sample,
  filename,
}: Props) {
  const [copied, setCopied] = useState(false);

  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-white">{title}</div>
          <div className="text-xs text-gray-500 mt-1 leading-5">
            {description}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={async () => {
              await navigator.clipboard.writeText(sample);
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1600);
            }}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 h-8 text-xs transition-colors ${
              copied
                ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
                : "border-gray-700 text-gray-300 hover:border-gray-500 hover:text-white"
            }`}
          >
            {copied ? <Check size={13} /> : <Copy size={13} />}
            {copied ? "已复制" : "复制"}
          </button>
          <button
            type="button"
            onClick={() => downloadTextFile(filename, sample)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-700 px-2.5 h-8 text-xs text-gray-300 hover:border-gray-500 hover:text-white transition-colors"
          >
            <Download size={13} />
            模板
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900/70 p-3">
        <div className="text-[11px] uppercase tracking-wide text-gray-500 mb-2">
          必填字段
        </div>
        <div className="flex flex-wrap gap-2">
          {fields.map((field) => (
            <span
              key={field}
              className="rounded-full border border-indigo-800/50 bg-indigo-950/30 px-2.5 py-1 text-xs text-indigo-300"
            >
              {field}
            </span>
          ))}
        </div>
      </div>

      <pre className="overflow-x-auto rounded-xl border border-gray-800 bg-black/30 p-3 text-[11px] leading-5 text-gray-300">
        <code>{sample}</code>
      </pre>
    </div>
  );
}
