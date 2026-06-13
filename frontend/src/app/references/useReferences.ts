"use client";

import { useState, useCallback, useEffect } from "react";
import { fetchApi } from "@/lib/api";

export interface ImplicitEdge {
    doc_a: string;
    doc_b: string;
    common_entities: string[];
    confidence: number;
}

export interface RefNode {
    id: string; title: string;
    ref_out_count: number; ref_in_count: number;
    is_center: boolean;
    x?: number; y?: number; fx?: number | null; fy?: number | null;
}

export interface RefEdge {
    source: string | RefNode;
    target: string | RefNode;
    weight: number;
}

export interface RefStats {
    total_docs: number;
    total_refs: number;
    most_cited: { doc_id: string; count: number } | null;
}

export function nodeRadius(n: RefNode) { return Math.min(8 + n.ref_in_count * 2, 36); }

export function nodeColor(n: RefNode) {
    if (n.is_center)         return "#22c55e";
    if (n.ref_in_count >= 5) return "#f59e0b";
    return "#6366f1";
}

export function useReferences() {
    const [nodes,          setNodes]          = useState<RefNode[]>([]);
    const [edges,          setEdges]          = useState<RefEdge[]>([]);
    const [implicitEdges,  setImplicitEdges]  = useState<ImplicitEdge[]>([]);
    const [showImplicit,   setShowImplicit]   = useState(false);
    const [stats,          setStats]          = useState<RefStats | null>(null);
    const [focusId,        setFocusId]        = useState("");
    const [depth,          setDepth]          = useState(1);
    const [search,         setSearch]         = useState("");
    const [selected,       setSelected]       = useState<RefNode | null>(null);
    const [loading,        setLoading]        = useState(true);

    const fetchData = useCallback(async (docId: string, d: number) => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (docId) params.set("doc_id", docId);
            params.set("depth", String(d));
            const data = await fetchApi<{ nodes: RefNode[]; edges: RefEdge[]; stats: RefStats }>(`/api/graph/references?${params}`);
            setNodes(data.nodes ?? []);
            setEdges(data.edges ?? []);
            setStats(data.stats ?? null);
        } catch (e) {
            console.error("fetch references failed", e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(focusId, depth); }, [focusId, depth, fetchData]);

    // 懒加载隐性关联
    useEffect(() => {
        if (!showImplicit || implicitEdges.length > 0) return;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        fetchApi<any>("/api/admin/associations")
            .then((d: { associations?: Array<ImplicitEdge & { is_implicit: boolean }> }) => {
                const implicit: ImplicitEdge[] = (d.associations ?? [])
                    .filter((a: { is_implicit: boolean }) => a.is_implicit)
                    .map((a: ImplicitEdge) => ({
                        doc_a: a.doc_a,
                        doc_b: a.doc_b,
                        common_entities: a.common_entities,
                        confidence: a.confidence,
                    }));
                setImplicitEdges(implicit);
            })
            .catch(() => {});
    }, [showImplicit, implicitEdges.length]);

    const filtered = search.trim()
        ? nodes.filter(n =>
            n.id.toLowerCase().includes(search.toLowerCase()) ||
            n.title.toLowerCase().includes(search.toLowerCase()))
        : [];

    const outNeighbors = selected
        ? edges.flatMap(e => {
            const s = typeof e.source === "string" ? e.source : (e.source as RefNode).id;
            const t = typeof e.target === "string" ? e.target : (e.target as RefNode).id;
            return s === selected.id ? [t] : [];
          })
        : [];

    const inNeighbors = selected
        ? edges.flatMap(e => {
            const s = typeof e.source === "string" ? e.source : (e.source as RefNode).id;
            const t = typeof e.target === "string" ? e.target : (e.target as RefNode).id;
            return t === selected.id ? [s] : [];
          })
        : [];

    return {
        nodes, edges, stats, focusId, setFocusId, depth, setDepth,
        search, setSearch, selected, setSelected, loading,
        filtered, outNeighbors, inNeighbors,
        implicitEdges, showImplicit, setShowImplicit,
    };
}
