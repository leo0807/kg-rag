"use client";

import type { QueryResult } from "../admin/cypher/useCypherBuilder";

export interface AdminCypherResultPanelProps {
  cypher: string;
  setCypher: (value: string) => void;
  running: boolean;
  result: QueryResult | null;
  execute: () => void;
}

function exportCSV(columns: string[], rows: Record<string, unknown>[]) {
  const esc = (v: unknown) =>
    JSON.stringify(typeof v === "object" ? JSON.stringify(v) : String(v ?? ""));
  const blob = new Blob(
    [
      columns.join(",") +
        "\n" +
        rows.map((r) => columns.map((c) => esc(r[c])).join(",")).join("\n"),
    ],
    { type: "text/csv" },
  );
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "cypher_result.csv";
  a.click();
}

export function AdminCypherResultPanel({
  cypher,
  setCypher,
  running,
  result,
  execute,
}: AdminCypherResultPanelProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="shrink-0 border-b border-gray-800 p-4">
        <textarea
          value={cypher}
          onChange={(e) => setCypher(e.target.value)}
          rows={6}
          spellCheck={false}
          className="w-full resize-none rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 font-mono text-xs text-green-300 outline-none focus:border-indigo-500"
        />
        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            onClick={execute}
            disabled={running || !cypher.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {running ? "执行中…" : "▶ 执行查询"}
          </button>
          {result && !result.error && (
            <span className="text-xs text-gray-500">
              返回 {result.total} 行（上限 100）
            </span>
          )}
          {result && !result.error && result.total > 0 && (
            <button
              type="button"
              onClick={() => exportCSV(result.columns, result.rows)}
              className="ml-auto rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-xs text-gray-400 hover:text-white"
            >
              导出 CSV
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-4">
        {result?.error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 font-mono text-xs whitespace-pre-wrap text-red-400">
            {result.error}
          </div>
        )}
        {result && !result.error && result.columns.length > 0 && (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-800 text-left text-gray-400">
                {result.columns.map((c) => (
                  <th key={c} className="pb-2 pr-4 font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, i) => (
                <tr
                  key={
                    result.columns
                      .map((c) => String(row[c] ?? ""))
                      .join("::") || `${i}`
                  }
                  className="border-b border-gray-800/40 hover:bg-gray-900/50"
                >
                  {result.columns.map((c) => (
                    <td key={c} className="max-w-xs py-1.5 pr-4 text-gray-300">
                      <span
                        className="block truncate"
                        title={
                          typeof row[c] === "object"
                            ? JSON.stringify(row[c])
                            : String(row[c] ?? "")
                        }
                      >
                        {typeof row[c] === "object"
                          ? JSON.stringify(row[c])
                          : String(row[c] ?? "—")}
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!result && (
          <div className="flex h-32 items-center justify-center text-sm text-gray-600">
            配置查询后点击执行
          </div>
        )}
      </div>
    </div>
  );
}
