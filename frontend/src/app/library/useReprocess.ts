"use client";

import { useEffect, useRef, useState } from "react";

export const PIPELINES = [
  { key: "reparse",     label: "重新解析章节", desc: "修复 0 章节文档（重新提取章节结构）" },
  { key: "images",      label: "图片补全",     desc: "重新提取图片节点并写入图谱" },
  { key: "entities",    label: "实体提取",     desc: "Tool / Material / Process 节点" },
  { key: "constraints", label: "约束参数",     desc: "LLM 提取力矩/公差/温度" },
  { key: "tables",      label: "表格提取",     desc: "PP-Structure → Constraint 节点" },
  { key: "drawings",    label: "工程图纸",     desc: "VLM 分析尺寸标注与装配关系" },
  { key: "defects",     label: "缺陷检测",     desc: "YOLOv11 视觉质检" },
] as const;
export type PK = typeof PIPELINES[number]["key"];

export interface Doc { doc_id: string; title: string | null; section_count: number; }
export interface Batch {
  status: string;
  total?: number; done?: number;
  current_doc?: string; current_step?: string; message?: string;
  pipelines?: string[];
  errors?: { doc_id: string; error: string }[];
  completed_docs?: string[];
  started_at?: number; finished_at?: number;
}

export function lsGet(key: string): string | null {
  if (typeof window === "undefined") return null;
  try { return localStorage.getItem(key); } catch { return null; }
}
export function lsSet(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch {}
}
export function lsRemove(key: string) {
  try { localStorage.removeItem(key); } catch {}
}
export function lsKeys(): string[] {
  if (typeof window === "undefined") return [];
  try { return Object.keys(localStorage); } catch { return []; }
}

export function fmtRemaining(secs: number): string {
  if (secs <= 0) return "";
  if (secs < 60) return "约 1 分钟";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `约 ${mins} 分钟`;
  const hrs = Math.floor(mins / 60);
  const rem = mins % 60;
  return rem > 0 ? `约 ${hrs} 小时 ${rem} 分钟` : `约 ${hrs} 小时`;
}

const LS_PIPELINES = "reparse:global_options";

export function useReprocess() {
  const [sel, setSel] = useState<Set<PK>>(() => {
    const stored = lsGet(LS_PIPELINES);
    if (stored) {
      try {
        const arr = JSON.parse(stored) as PK[];
        const valid = arr.filter(k => PIPELINES.some(p => p.key === k));
        if (valid.length > 0) return new Set(valid);
      } catch {}
    }
    return new Set<PK>(["images", "entities", "constraints", "tables", "drawings"]);
  });

  const [docs, setDocs] = useState<Doc[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [docSearch, setDocSearch] = useState("");
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(() => {
    const ids = lsKeys().filter(k => k.startsWith("reparse:doc:")).map(k => k.replace("reparse:doc:", ""));
    return new Set(ids);
  });
  const [batch, setBatch] = useState<Batch>(() => {
    try {
      const stored = sessionStorage.getItem("kg_batch_status");
      return stored ? (JSON.parse(stored) as Batch) : { status: "idle" };
    } catch { return { status: "idle" }; }
  });
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") ?? "" : "";
  const h = { "Content-Type": "application/json", Authorization: `Bearer ${token}` };

  function updateBatch(next: Batch | ((prev: Batch) => Batch)) {
    setBatch(prev => {
      const val = typeof next === "function" ? next(prev) : next;
      try { sessionStorage.setItem("kg_batch_status", JSON.stringify(val)); } catch {}
      return val;
    });
  }

  async function fetchDocs() {
    setDocsLoading(true);
    try {
      const PER = 500;
      const first = await fetch(`/api/documents?per_page=${PER}&page=1`, { headers: h }).then(r => r.json());
      let all: Doc[] = first.data ?? [];
      const pages: number = first.pages ?? 1;
      if (pages > 1) {
        const rest = await Promise.all(
          Array.from({ length: pages - 1 }, (_, i) =>
            fetch(`/api/documents?per_page=${PER}&page=${i + 2}`, { headers: h }).then(r => r.json())
          )
        );
        for (const d of rest) all = all.concat(d.data ?? []);
      }
      setDocs(all);
    } finally { setDocsLoading(false); }
  }

  useEffect(() => { fetchDocs(); }, []);
  useEffect(() => { lsSet(LS_PIPELINES, JSON.stringify([...sel])); }, [sel]);
  useEffect(() => {
    lsKeys().filter(k => k.startsWith("reparse:doc:")).forEach(lsRemove);
    selectedDocs.forEach(id => lsSet(`reparse:doc:${id}`, "1"));
  }, [selectedDocs]);
  useEffect(() => {
    fetch("/api/documents/reprocess-all/status", { headers: h })
      .then(r => r.json()).then(updateBatch).catch(() => {});
  }, []);
  useEffect(() => { if (batch.status === "completed") fetchDocs(); }, [batch.status]);
  useEffect(() => {
    if (batch.status === "running") {
      pollRef.current = setInterval(async () => {
        const r = await fetch("/api/documents/reprocess-all/status", { headers: h });
        const d: Batch = await r.json();
        updateBatch(d);
        if (d.status !== "running") clearInterval(pollRef.current!);
      }, 3000);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [batch.status]);

  const filteredDocs = docs.filter(d =>
    !docSearch ||
    d.doc_id.toLowerCase().includes(docSearch.toLowerCase()) ||
    (d.title ?? "").toLowerCase().includes(docSearch.toLowerCase())
  );
  const allSelected = filteredDocs.length > 0 && filteredDocs.every(d => selectedDocs.has(d.doc_id));
  const someSelected = selectedDocs.size > 0;

  function toggleDoc(id: string) {
    setSelectedDocs(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }
  function toggleAll() {
    if (allSelected) {
      setSelectedDocs(prev => { const n = new Set(prev); filteredDocs.forEach(d => n.delete(d.doc_id)); return n; });
    } else {
      setSelectedDocs(prev => { const n = new Set(prev); filteredDocs.forEach(d => n.add(d.doc_id)); return n; });
    }
  }

  async function start() {
    setConfirm(false); setBusy(true);
    updateBatch({ status: "running", total: someSelected ? selectedDocs.size : docs.length, done: 0, pipelines: [...sel] });
    try {
      const body: Record<string, unknown> = { pipelines: [...sel] };
      if (someSelected) body.doc_ids = [...selectedDocs];
      const r = await fetch("/api/documents/reprocess-all", { method: "POST", headers: h, body: JSON.stringify(body) });
      const d = await r.json();
      if (d.status === "started" || d.status === "running") {
        updateBatch(prev => ({ ...prev, total: d.total }));
        lsKeys().filter(k => k.startsWith("reparse:doc:")).forEach(lsRemove);
        setSelectedDocs(new Set());
      } else {
        updateBatch({ status: "idle" });
      }
    } catch { updateBatch({ status: "idle" }); }
    finally { setBusy(false); }
  }

  async function cancel() {
    await fetch("/api/documents/reprocess-all/cancel", { method: "POST", headers: h });
    updateBatch(b => ({ ...b, status: "cancelling" }));
  }

  async function resume() {
    setBusy(true);
    try {
      const body: Record<string, unknown> = { pipelines: [...sel] };
      if (someSelected) body.doc_ids = [...selectedDocs];
      const r = await fetch("/api/documents/reprocess-all/resume", { method: "POST", headers: h, body: JSON.stringify(body) });
      const d = await r.json();
      if (d.status === "resumed") updateBatch(b => ({ ...b, status: "running" }));
    } finally { setBusy(false); }
  }

  async function clearBatch() {
    await fetch("/api/documents/reprocess-all/clear", { method: "POST", headers: h });
    updateBatch({ status: "idle" });
  }

  return {
    sel, setSel, docs, docsLoading, docSearch, setDocSearch,
    selectedDocs, filteredDocs, allSelected, someSelected,
    batch, busy, confirm, setConfirm, token, h,
    toggleDoc, toggleAll, clearSelection: () => setSelectedDocs(new Set()),
    start, cancel, resume, clearBatch,
  };
}
