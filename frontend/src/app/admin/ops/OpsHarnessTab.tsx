"use client";

import { ArrowRight, CircleHelp, FileSearch, GitBranch, Loader2, Wrench } from "lucide-react";
import { useState } from "react";
import { fetchApi } from "@/lib/api";
import type { HarnessResult } from "./useOpsData";

interface Props {
  onAfterRun: () => void;
}

const EXAMPLES = [
  "CPS1000 的工程图纸主要讲了什么？",
  "CPS0205 第 7 章和取样相关的要求有哪些？",
  "CPS0100 里有哪些工装和材料约束？",
];

export function OpsHarnessTab({ onAfterRun }: Props) {
  const [question, setQuestion] = useState("CPS1000 的工程图纸主要讲了什么？");
  const [docId, setDocId] = useState("CPS1000");
  const [topK, setTopK] = useState(5);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<HarnessResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    try {
      setLoading(true); setError(null);
      const data = await fetchApi<HarnessResult>("/api/admin/ops/harness/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, doc_id: docId.trim(), top_k: topK }),
      });
      setResult(data);
      onAfterRun();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Harness 执行失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="mb-5 flex items-center gap-3">
        <div className="rounded-xl bg-indigo-500/10 p-2"><Wrench size={18} className="text-indigo-300" /></div>
        <div>
          <h3 className="text-lg font-semibold text-white">Harness 调度台</h3>
          <p className="text-xs text-gray-500">自动规划策略，并把章节证据和图纸证据一起拉平展示。</p>
        </div>
      </div>
      <div className="mb-5 grid grid-cols-1 gap-3 lg:grid-cols-3">
        {[
          { title: "策略规划", text: "先根据问题意图决定走章节检索、图纸补证还是混合策略。", Icon: GitBranch },
          { title: "证据拉平", text: "把章节证据和图片/工程图纸证据放到同一结果面板里对齐展示。", Icon: FileSearch },
          { title: "工程回归", text: "适合验证 CPS 文档在真实问题下的检索命中、证据完整性和回答质量。", Icon: ArrowRight },
        ].map(({ title, text, Icon }) => (
          <div key={title} className="rounded-2xl border border-gray-800 bg-gray-950/60 p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium text-white"><Icon size={15} className="text-indigo-300" />{title}</div>
            <div className="text-xs leading-6 text-gray-500">{text}</div>
          </div>
        ))}
      </div>
      <div className="mb-5 rounded-2xl border border-indigo-500/15 bg-indigo-500/5 p-4">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-white"><CircleHelp size={15} className="text-indigo-300" />快速上手</div>
        <div className="mb-3 text-xs leading-6 text-gray-400">先输入一个真实业务问题。若你已经知道目标文档，就填 `doc_id` 缩小范围；若想让系统自动全库规划，可以留空。`Top K` 越大，候选证据越多，但噪声也可能增加。</div>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" onClick={() => setQuestion(ex)}
              className="rounded-full border border-gray-700 bg-gray-950/80 px-3 py-1.5 text-xs text-gray-300 transition-colors hover:border-indigo-400/50 hover:text-white">{ex}</button>
          ))}
        </div>
      </div>
      {error && <div className="mb-4 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <label className="block">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.24em] text-gray-500">
            问题输入 <span className="rounded-full border border-gray-700 px-2 py-0.5 text-[10px] tracking-normal text-gray-400">输入待验证问题</span>
          </div>
          <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={4}
            className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm leading-7 text-gray-100 outline-none placeholder:text-gray-600"
            placeholder="输入一个复杂问题，例如 CPS1000 的工程图纸主要讲了什么？" />
        </label>
        <div className="rounded-2xl border border-gray-800 bg-gray-950/60 p-4">
          <div className="grid grid-cols-1 gap-4">
            <label className="block">
              <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.24em] text-gray-500">限定文档 <span className="rounded-full border border-gray-700 px-2 py-0.5 text-[10px] tracking-normal text-gray-400">选填</span></div>
              <input value={docId} onChange={(e) => setDocId(e.target.value)} className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none placeholder:text-gray-600" placeholder="如 CPS1000，可留空" />
              <div className="mt-2 text-xs text-gray-600">填写后只在目标文档内规划和取证。</div>
            </label>
            <label className="block">
              <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.24em] text-gray-500">Top K <span className="rounded-full border border-gray-700 px-2 py-0.5 text-[10px] tracking-normal text-gray-400">候选证据数</span></div>
              <input type="number" min={1} max={10} value={topK} onChange={(e) => setTopK(Number(e.target.value || 5))} className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none" />
              <div className="mt-2 text-xs text-gray-600">控制候选证据数量，默认 5。</div>
            </label>
            <button type="button" onClick={run} disabled={loading || !question.trim()} className="inline-flex h-12 items-center justify-center rounded-2xl bg-indigo-600 px-4 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">
              {loading ? <Loader2 size={16} className="animate-spin" /> : "运行 Harness"}
            </button>
            <div className="text-xs leading-6 text-gray-600">输出会包含策略判断、章节证据、图纸/图片证据，以及最终汇总回答。</div>
          </div>
        </div>
      </div>
      {result && (
        <div className="mt-6 space-y-4">
          <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/10 p-4">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-full bg-indigo-500/20 px-2 py-1 text-indigo-200">{result.plan.strategy}</span>
              {result.plan.intents.map((intent) => <span key={intent} className="rounded-full bg-gray-800 px-2 py-1 text-gray-300">{intent}</span>)}
            </div>
            <div className="mt-3 text-sm text-gray-200">{result.plan.reason}</div>
            <div className="mt-3 rounded-xl bg-gray-950/70 p-4 text-sm leading-7 text-gray-100">{result.answer}</div>
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-gray-800 bg-gray-950/50 p-4">
              <div className="mb-3 text-xs uppercase tracking-[0.2em] text-gray-500">章节证据 {result.runtime.section_hits}</div>
              <div className="space-y-3">
                {result.section_sources.slice(0, 5).map((s) => (
                  <div key={s.chunk_id} className="rounded-xl border border-gray-800 bg-gray-900/70 p-3">
                    <div className="text-sm font-medium text-white">{s.doc_id} §{s.number} {s.title}</div>
                    <div className="mt-1 text-xs text-gray-500">score {s.score} · {s.retrieval_trace.join(" / ") || "no-trace"}</div>
                    <div className="mt-2 line-clamp-4 text-sm leading-6 text-gray-300">{s.content}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border border-gray-800 bg-gray-950/50 p-4">
              <div className="mb-3 text-xs uppercase tracking-[0.2em] text-gray-500">图片/图纸证据 {result.runtime.image_hits}</div>
              <div className="space-y-3">
                {result.image_sources.length === 0 && <div className="rounded-xl border border-dashed border-gray-800 px-4 py-6 text-sm text-gray-500">当前问题没有补充到额外图片证据。</div>}
                {result.image_sources.map((img) => (
                  <div key={img.image_id} className="rounded-xl border border-gray-800 bg-gray-900/70 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium text-white">{img.doc_id} #{img.image_id}</div>
                      <span className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-widest ${img.is_drawing ? "bg-emerald-500/10 text-emerald-300" : "bg-gray-800 text-gray-300"}`}>{img.is_drawing ? "drawing" : "image"}</span>
                    </div>
                    <div className="mt-2 text-sm leading-6 text-gray-300">{img.summary || img.caption || "暂无摘要"}</div>
                    <div className="mt-2 text-xs text-gray-500">关键词命中 {img.keyword_hits}{img.section_number ? ` · 章节 ${img.section_number}` : ""}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
