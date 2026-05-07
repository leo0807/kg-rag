"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

interface Props {
  text: string;
}

export function AssistantMessageActions({ text }: Props) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1400);
    return () => clearTimeout(timer);
  }, [copied]);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      void 0;
    }
  }

  return (
    <div className="absolute right-2 top-2 flex items-center gap-1.5 opacity-0 transition-opacity group-hover:opacity-100">
      <button
        type="button"
        onClick={handleCopy}
        className="inline-flex h-8 items-center gap-1 rounded-lg border border-gray-700/80 bg-gray-950/95 px-2.5 text-[11px] text-gray-400 shadow-sm transition-colors hover:border-gray-500 hover:text-gray-200"
        title="复制回复"
        aria-label={copied ? "已复制回复" : "复制回复"}
      >
        {copied ? (
          <Check size={12} className="text-emerald-400" />
        ) : (
          <Copy size={12} />
        )}
        {copied ? "已复制" : "复制"}
      </button>
    </div>
  );
}
