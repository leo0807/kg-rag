"use client";

interface ConstraintResult {
  chunk_id: string; doc_id: string; number: string; title: string;
  c_type: string; value: string; value_min: string; value_max: string;
  unit: string; description: string;
}

function ResultCount({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-gray-500">
      <span className="px-2 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-full font-medium">{n}</span>
      {label}
    </div>
  );
}

export function ConstraintResults({ results }: { results: ConstraintResult[] }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-800">
        <ResultCount n={results.length} label="条约束参数" />
      </div>
      <div className="divide-y divide-gray-800/60 max-h-[480px] overflow-y-auto">
        {results.length === 0 ? (
          <div className="py-14 text-center text-gray-600 text-sm">暂无匹配的约束参数</div>
        ) : results.map(r => (
          <div key={r.chunk_id} className="px-5 py-4 hover:bg-gray-800/30 transition-colors">
            <div className="flex items-start justify-between gap-3 mb-1.5">
              <span className="text-xs font-mono text-indigo-400">{r.doc_id} § {r.number}</span>
              <span className="shrink-0 px-2 py-0.5 rounded-full text-xs bg-emerald-900/40 text-emerald-400 border border-emerald-700/30 font-mono">
                {r.c_type} · {r.value_min || r.value}{r.value_max ? `~${r.value_max}` : ""} {r.unit}
              </span>
            </div>
            <div className="text-sm text-gray-200 font-medium">{r.title}</div>
            {r.description && <div className="text-xs text-gray-500 mt-1 leading-relaxed">{r.description}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

export type { ConstraintResult };
