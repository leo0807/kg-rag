"use client";

import type { ReactNode } from "react";

type Props = {
  label: string;
  children: ReactNode;
};

export function PromptField({ label, children }: Props) {
  return (
    <div className="space-y-1 text-sm text-slate-300">
      <span className="block text-xs text-slate-500">{label}</span>
      {children}
    </div>
  );
}
