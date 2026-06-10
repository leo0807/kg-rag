"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

interface LinkSpan {
  start: number;
  end: number;
  text: string;
  kind: "cps" | "term";
  href: string;
  tooltip: string;
}

interface Props {
  text: string;
  links: LinkSpan[];
}

/** Renders plain text with inline CPS / term links + hover tooltips. */
export function TermTooltip({ text, links }: Props) {
  if (!links.length) return <span>{text}</span>;

  const parts: React.ReactNode[] = [];
  let cursor = 0;

  for (const lnk of links) {
    if (lnk.start > cursor) parts.push(text.slice(cursor, lnk.start));
    parts.push(
      <InlineLink key={`${lnk.start}-${lnk.end}`} lnk={lnk} />
    );
    cursor = lnk.end;
  }
  if (cursor < text.length) parts.push(text.slice(cursor));

  return <span>{parts}</span>;
}

function InlineLink({ lnk }: { lnk: LinkSpan }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const isCps = lnk.kind === "cps";

  return (
    <span ref={ref} className="relative inline-block">
      <Link
        href={lnk.href}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className={`border-b border-dashed cursor-pointer transition-colors ${
          isCps
            ? "text-indigo-400 border-indigo-700 hover:text-indigo-300"
            : "text-emerald-400 border-emerald-800 hover:text-emerald-300"
        }`}
      >
        {lnk.text}
      </Link>

      {open && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50
                         w-max max-w-[220px] px-3 py-2 rounded-lg shadow-lg
                         bg-gray-800 border border-gray-700 text-xs text-gray-200
                         pointer-events-none whitespace-normal leading-relaxed">
          {lnk.tooltip}
          {/* arrow */}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-700" />
        </span>
      )}
    </span>
  );
}
