"use client";

import { useEffect, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";
import { Globe, Layers, Loader2, Play } from "lucide-react";

interface Doc { doc_id: string; title?: string }
interface Props { onGenerated: (graphId: string) => void }

export function SPOGeneratePanel({ onGenerated }: Props) {
  const [docs,    setDocs]    = useState<Doc[]>([]);
  const [docId,   setDocId]   = useState("");
  const [chapter, setChapter] = useState("6");
  const [jobId,   setJobId]   = useState<string | null>(null);
  const [status,  setStatus]  = useState<string>("");
  const [busy,    setBusy]    = useState(false);
  const [batchBusy,   setBatchBusy]   = useState(false);
  const [batchStatus, setBatchStatus] = useState<string>("");
  const batchJobId = useRef<string | null>(null);
  const [globalBusy,   setGlobalBusy]   = useState(false);
  const [globalStatus, setGlobalStatus] = useState<string>("");
  const [maxSections,  setMaxSections]  = useState("200");
  const globalJobId = useRef<string | null>(null);

  useEffect(() => {
    fetchApi<{ data?: Doc[] }>("/api/documents?per_page=500")
      .then(d => { setDocs(d.data ?? []); if (d.data?.[0]) setDocId(d.data[0].doc_id); })
      .catch(() => {});
  }, []);

  // Poll single-doc job
  useEffect(() => {
    if (!jobId) return;
    const timer = setInterval(async () => {
      try {
        const job = await fetchApi<{ status: string; message?: string; graph_id?: string }>(`/api/graph/spo/jobs/${jobId}`);
        setStatus(job.message ?? job.status);
        if (job.status === "completed") {
          clearInterval(timer);
          setBusy(false); setJobId(null); setStatus("");
          if (job.graph_id) onGenerated(job.graph_id);
        } else if (job.status === "failed") {
          clearInterval(timer); setBusy(false); setJobId(null);
        }
      } catch { clearInterval(timer); setBusy(false); setJobId(null); }
    }, 2000);
    return () => clearInterval(timer);
  }, [jobId, onGenerated]);

  // Poll batch job
  useEffect(() => {
    if (!batchBusy) return;
    const timer = setInterval(async () => {
      const bjid = batchJobId.current;
      if (!bjid) return;
      try {
        const job = await fetchApi<{ status: string; message?: string; progress?: number; total?: number; generated?: string[] }>(`/api/graph/spo/jobs/${bjid}`);
        setBatchStatus(job.message ?? job.status);
        if (job.status === "completed") {
          clearInterval(timer); setBatchBusy(false); setBatchStatus("");
          if (job.generated?.length) onGenerated(job.generated[0]);
        } else if (job.status === "failed") {
          clearInterval(timer); setBatchBusy(false);
        }
      } catch { clearInterval(timer); setBatchBusy(false); }
    }, 3000);
    return () => clearInterval(timer);
  }, [batchBusy, onGenerated]);

  // Poll global graph job
  useEffect(() => {
    if (!globalBusy) return;
    const timer = setInterval(async () => {
      const jid = globalJobId.current;
      if (!jid) return;
      try {
        const job = await fetchApi<{ status: string; message?: string; graph_id?: string; progress?: number; total?: number }>(`/api/graph/spo/jobs/${jid}`);
        const pct = job.total ? ` (${job.progress}/${job.total})` : "";
        setGlobalStatus((job.message ?? job.status) + pct);
        if (job.status === "completed") {
          clearInterval(timer); setGlobalBusy(false); setGlobalStatus("");
          if (job.graph_id) onGenerated(job.graph_id);
        } else if (job.status === "failed") {
          clearInterval(timer); setGlobalBusy(false);
        }
      } catch { clearInterval(timer); setGlobalBusy(false); }
    }, 3000);
    return () => clearInterval(timer);
  }, [globalBusy, onGenerated]);

  async function handleGlobalGenerate() {
    setGlobalBusy(true); setGlobalStatus("提交任务…");
    try {
      const res = await fetchApi<{ job_id: string; graph_id: string }>("/api/graph/spo/generate-global", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_sections: parseInt(maxSections) || 200 }),
      });
      globalJobId.current = res.job_id;
      setGlobalStatus("构建中…");
    } catch { setGlobalBusy(false); setGlobalStatus("提交失败"); }
  }

  async function handleGenerate() {
    if (!docId) return;
    setBusy(true); setStatus("提交任务中…");
    try {
      const res = await fetchApi<{ graph_id: string }>("/api/graph/spo/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id: docId, chapter }),
      });
      setJobId(res.graph_id); setStatus("排队中…");
    } catch { setBusy(false); setStatus("提交失败"); }
  }

  async function handleBatchAll() {
    setBatchBusy(true); setBatchStatus("提交批量任务…");
    try {
      const res = await fetchApi<{ job_id: string }>("/api/graph/spo/generate-all-docs", { method: "POST" });
      batchJobId.current = res.job_id; setBatchStatus("批量任务排队中…");
    } catch { setBatchBusy(false); setBatchStatus("提交失败"); }
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      <p className="text-white text-sm font-medium">生成新 SPO 图谱</p>

      {/* Single-doc generation */}
      <div className="space-y-2">
        <div>
          <label className="text-xs text-gray-500 block mb-1">选择文档</label>
          <select value={docId} onChange={e => setDocId(e.target.value)}
            className="w-full px-2.5 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500">
            {docs.map(d => <option key={d.doc_id} value={d.doc_id}>{d.title || d.doc_id}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">章节（输入编号或选全文）</label>
          <div className="flex gap-1.5">
            <input value={chapter} onChange={e => setChapter(e.target.value)}
              placeholder="如 6 或 2.1"
              className="flex-1 min-w-0 px-2.5 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500" />
            <button type="button" onClick={() => setChapter("ALL")}
              className={`px-2.5 py-1.5 rounded text-xs border transition-colors ${chapter === "ALL" ? "bg-indigo-600 border-indigo-500 text-white" : "bg-gray-800 border-gray-700 text-gray-400 hover:text-white"}`}>
              全文
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <button onClick={handleGenerate} disabled={busy || !docId}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
            {busy ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            {busy ? "生成中…" : "开始生成"}
          </button>
          {status && <span className="text-xs text-gray-400 truncate">{status}</span>}
        </div>
      </div>

      {/* Batch all docs */}
      <div className="border-t border-gray-800 pt-2">
        <p className="text-xs text-gray-500 mb-2">批量生成（所有文档全文）</p>
        <div className="flex items-center gap-2.5">
          <button onClick={handleBatchAll} disabled={batchBusy || busy || globalBusy}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
            {batchBusy ? <Loader2 size={13} className="animate-spin" /> : <Layers size={13} />}
            {batchBusy ? "批量生成中…" : "全部文档"}
          </button>
          {batchStatus && <span className="text-xs text-gray-400 truncate">{batchStatus}</span>}
        </div>
      </div>

      {/* Global graph (spo_global) */}
      <div className="border-t border-gray-800 pt-2">
        <p className="text-xs text-gray-500 mb-1">全局知识图谱 <span className="text-indigo-400">spo_global</span></p>
        <p className="text-xs text-gray-600 mb-2">从所有文档最丰富的章节提取，增量写入同一张图</p>
        <div className="flex items-center gap-2">
          <input
            type="number" min="50" max="2000" value={maxSections}
            onChange={e => setMaxSections(e.target.value)}
            className="w-20 px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-gray-200 outline-none focus:border-indigo-500"
          />
          <span className="text-xs text-gray-500">节</span>
          <button onClick={handleGlobalGenerate} disabled={globalBusy || busy || batchBusy}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-700 hover:bg-indigo-600 text-white text-sm rounded-lg disabled:opacity-50 transition-colors">
            {globalBusy ? <Loader2 size={13} className="animate-spin" /> : <Globe size={13} />}
            {globalBusy ? "构建中…" : "构建全局图谱"}
          </button>
        </div>
        {globalStatus && <p className="text-xs text-gray-400 mt-1.5 truncate">{globalStatus}</p>}
      </div>
    </div>
  );
}
