"use client";

import { useEffect, useRef, useState } from "react";
import { fetchApi, getAuthHeaders } from "@/lib/api";

const API = "http://localhost:8000";

export type Severity = "high" | "medium" | "low";
export type ConflictType = "constraint" | "semantic";
export type Status = "pending" | "confirmed" | "dismissed" | "resolved";

export interface ConflictItem {
    id: number;
    scan_id: string;
    conflict_type: ConflictType;
    severity: Severity;
    entity_name: string;
    entity_type: string;
    section_a_chunk_id: string;
    section_a_doc_id: string;
    section_a_title: string;
    section_a_snippet: string;
    section_b_chunk_id: string;
    section_b_doc_id: string;
    section_b_title: string;
    section_b_snippet: string;
    description: string;
    status: Status;
    created_at: string | null;
}

export interface ScanRecord {
    scan_id: string;
    status: string;
    phase: string;
    constraint_count: number;
    semantic_count: number;
    entity_pairs_total: number;
    entity_pairs_done: number;
    total_conflicts: number;
    error: string;
    created_at: string;
    started_at: string | null;
    finished_at: string | null;
}

export interface Stats {
    total: number;
    by_status: Record<string, number>;
    by_severity: Record<string, number>;
    by_type: Record<string, number>;
}

export const SEVERITY_STYLE: Record<Severity, string> = {
    high: "bg-rose-500/15 text-rose-400 border border-rose-500/30",
    medium: "bg-amber-500/15 text-amber-400 border border-amber-500/30",
    low: "bg-blue-500/15 text-blue-400 border border-blue-500/30",
};

export const STATUS_STYLE: Record<Status, string> = {
    pending: "bg-gray-700/60 text-gray-300",
    confirmed: "bg-rose-700/40 text-rose-300",
    dismissed: "bg-gray-800 text-gray-500",
    resolved: "bg-emerald-700/40 text-emerald-300",
};

export const STATUS_LABELS: Record<Status, string> = {
    pending: "待审核",
    confirmed: "已确认",
    dismissed: "已忽略",
    resolved: "已解决",
};

export function useConflicts() {
    const [scan, setScan] = useState<ScanRecord | null>(null);
    const [scanning, setScanning] = useState(false);
    const [conflicts, setConflicts] = useState<ConflictItem[]>([]);
    const [total, setTotal] = useState(0);
    const [stats, setStats] = useState<Stats | null>(null);
    const [filterStatus, setFilterStatus] = useState("");
    const [filterSeverity, setFilterSeverity] = useState("");
    const [filterType, setFilterType] = useState("");
    const [expanded, setExpanded] = useState<Set<number>>(new Set());
    const [error, setError] = useState<string | null>(null);
    const [updating, setUpdating] = useState<number | null>(null);
    const scanTimerRef = useRef<number | null>(null);

    async function loadConflicts() {
        const params = new URLSearchParams({ limit: "200" });
        if (filterStatus) params.set("status", filterStatus);
        if (filterSeverity) params.set("severity", filterSeverity);
        if (filterType) params.set("conflict_type", filterType);
        try {
            const data = await fetchApi<{ total: number; items: ConflictItem[] }>(
                `${API}/api/admin/conflicts?${params}`,
            );
            setConflicts(data.items);
            setTotal(data.total);
        } catch {}
    }

    async function loadStats() {
        try {
            const data = await fetchApi<Stats>(`${API}/api/admin/conflicts/stats`);
            setStats(data);
        } catch {}
    }

    async function pollScan(scanId: string) {
        try {
            const data = await fetchApi<ScanRecord>(`${API}/api/admin/conflicts/scan/${scanId}`);
            setScan(data);
            if (data.status === "completed" || data.status === "failed") {
                if (scanTimerRef.current) { window.clearInterval(scanTimerRef.current); scanTimerRef.current = null; }
                if (data.status === "completed") await Promise.all([loadConflicts(), loadStats()]);
            }
        } catch {}
    }

    async function startScan() {
        setScanning(true);
        setError(null);
        try {
            const headers = await getAuthHeaders({ "Content-Type": "application/json" });
            const res = await fetch(`${API}/api/admin/conflicts/scan`, { method: "POST", headers });
            if (!res.ok) throw new Error((await res.json()).detail || "启动失败");
            const data: ScanRecord = await res.json();
            setScan(data);
            if (scanTimerRef.current) window.clearInterval(scanTimerRef.current);
            scanTimerRef.current = window.setInterval(() => pollScan(data.scan_id), 2000);
        } catch (e) {
            setError(e instanceof Error ? e.message : "启动扫描失败");
        } finally {
            setScanning(false);
        }
    }

    async function changeStatus(id: number, status: Status) {
        setUpdating(id);
        try {
            const headers = await getAuthHeaders({ "Content-Type": "application/json" });
            const res = await fetch(`${API}/api/admin/conflicts/${id}/status`, {
                method: "PATCH", headers, body: JSON.stringify({ status }),
            });
            if (!res.ok) throw new Error("更新失败");
            setConflicts(prev => prev.map(c => c.id === id ? { ...c, status } : c));
            loadStats();
        } catch (e) {
            setError(e instanceof Error ? e.message : "更新失败");
        } finally {
            setUpdating(null);
        }
    }

    function toggleExpand(id: number) {
        setExpanded(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    }

    useEffect(() => {
        loadConflicts();
        loadStats();
        return () => { if (scanTimerRef.current) window.clearInterval(scanTimerRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => { loadConflicts(); }, [filterStatus, filterSeverity, filterType]); // eslint-disable-line react-hooks/exhaustive-deps

    return {
        scan, scanning, conflicts, total, stats, error,
        filterStatus, setFilterStatus, filterSeverity, setFilterSeverity,
        filterType, setFilterType, expanded, updating,
        startScan, loadConflicts, loadStats, changeStatus, toggleExpand,
    };
}
