"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";

export interface CrossRefResult { doc_id: string; doc_title: string; chunk_id: string; number: string; title: string }

function ResultCount({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-gray-500">
      <span className="px-2 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-full font-medium">{n}</span>
      {label}
    </div>
  );
}

export function CrossRefResults({ results }: { results: CrossRefResult[] }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800">
        <ResultCount n={results.length} label="个章节引用了此规范" />
      </div>
      <div className="divide-y divide-gray-800/60 max-h-[480px] overflow-y-auto">
        {results.length === 0 ? (
          <div className="py-14 text-center text-gray-600 text-sm">暂无引用记录</div>
        ) : results.map(r => (
          <div key={r.chunk_id} className="px-5 py-4 hover:bg-gray-800/30 transition-colors group">
            <div className="flex items-start justify-between gap-3 mb-1.5">
              <span className="text-xs font-mono text-indigo-400">{r.doc_title} § {r.number}</span>
              <Link href={`/library/${r.doc_id}`}
                className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300">
                查看 <ChevronRight size={10} />
              </Link>
            </div>
            <div className="text-sm text-gray-300">{r.title}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
