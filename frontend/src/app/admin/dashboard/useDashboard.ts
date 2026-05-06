"use client";

import { useEffect, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";

export interface ServiceStatus {
    is_ok: boolean;
    latency_ms?: number;
    error?: string;
}

export interface MemoryInfo {
    total_gb:      number;
    used_gb:       number;
    available_gb:  number;
    percent:       number;
    models_loaded: { name: string; idle_secs: number; age_secs: number }[];
}

export interface DashboardData {
    health_score: number;
    graph: {
        node_count: number;
        rel_count: number;
        orphan_count: number;
        health_score: number;
    };
    llm: {
        queries_7d: number;
        avg_latency_ms: number;
        cost_usd_7d: number;
    };
    trend: { date: string; requests: number; avg_latency_ms: number }[];
    services: Record<string, ServiceStatus>;
    conflict_pending: number;
    actions: { type: string; label: string; href: string }[];
    recent_events: { action: string; resource: string; username: string; created_at: string }[];
    memory?: MemoryInfo;
}

export function useDashboard() {
    const [data, setData] = useState<DashboardData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
    const timerRef = useRef<number | null>(null);

    async function load() {
        try {
            const d = await fetchApi<DashboardData>("/api/admin/health");
            setData(d);
            setError(null);
            setLastRefresh(new Date());
        } catch (e) {
            setError(e instanceof Error ? e.message : "加载失败");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        load();
        timerRef.current = window.setInterval(load, 30_000);
        return () => { if (timerRef.current) window.clearInterval(timerRef.current); };
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    return { data, loading, error, lastRefresh, refresh: load };
}
