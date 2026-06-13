"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";

export interface FavoriteItem {
    id:         string;
    type:       "section" | "document" | "query";
    doc_id:     string | null;
    section_id: string | null;
    query_text: string | null;
    title:      string;
    note:       string | null;
    created_at: string;
}

interface CreateParams {
    type:       "section" | "document" | "query";
    doc_id?:    string;
    section_id?: string;
    query_text?: string;
    title:      string;
    note?:      string;
}

export function useFavorites() {
    const [favorites, setFavorites] = useState<FavoriteItem[]>([]);
    const [loaded,    setLoaded]    = useState(false);

    const fetchAll = useCallback(async () => {
        try {
            const data = await fetchApi<FavoriteItem[]>("/api/favorites");
            setFavorites(data);
        } catch { /* ignore */ }
        finally { setLoaded(true); }
    }, []);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    function getFavoriteId(params: {
        section_id?:  string;
        doc_id?:      string;
        query_text?:  string;
        type:         string;
    }): string | null {
        for (const f of favorites) {
            if (params.type === "section"  && f.section_id === params.section_id)  return f.id;
            if (params.type === "document" && f.doc_id     === params.doc_id && f.type === "document") return f.id;
            if (params.type === "query"    && f.query_text === params.query_text)  return f.id;
        }
        return null;
    }

    async function addFavorite(params: CreateParams): Promise<string | null> {
        try {
            const data = await fetchApi<FavoriteItem>("/api/favorites", {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify(params),
            });
            setFavorites(prev => {
                if (prev.some(f => f.id === data.id)) return prev;
                return [data, ...prev];
            });
            return data.id;
        } catch { return null; }
    }

    async function removeFavorite(favId: string): Promise<boolean> {
        try {
            await fetchApi(`/api/favorites/${favId}`, { method: "DELETE" });
            setFavorites(prev => prev.filter(f => f.id !== favId));
            return true;
        } catch { return false; }
    }

    async function patchNote(favId: string, note: string | null): Promise<boolean> {
        try {
            const data = await fetchApi<FavoriteItem>(`/api/favorites/${favId}`, {
                method:  "PATCH",
                headers: { "Content-Type": "application/json" },
                body:    JSON.stringify({ note }),
            });
            setFavorites(prev => prev.map(f => f.id === favId ? data : f));
            return true;
        } catch { return false; }
    }

    return { favorites, loaded, getFavoriteId, addFavorite, removeFavorite, patchNote, refresh: fetchAll };
}
