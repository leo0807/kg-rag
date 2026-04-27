"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, MessageSquarePlus, Trash2 } from "lucide-react";
import { fetchApi } from "@/lib/api";

interface Annotation {
    id:         number;
    node_id:    string;
    node_type:  string;
    user_id:    string;
    username:   string;
    full_name:  string;
    content:    string;
    created_at: string;
    updated_at: string;
}

function currentUser() {
    try { return JSON.parse(localStorage.getItem("user") ?? "{}"); } catch { return {}; }
}

interface Props { nodeId: string; nodeType: string; }

export function AnnotationPanel({ nodeId, nodeType }: Props) {
    const [annotations, setAnnotations] = useState<Annotation[]>([]);
    const [loading, setLoading]         = useState(false);
    const [draft, setDraft]             = useState("");
    const [submitting, setSubmitting]   = useState(false);
    const [error, setError]             = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const u = currentUser();
    const currentUserId: string = u.id ?? "";
    const isAdmin: boolean = u.is_admin ?? false;

    useEffect(() => {
        let cancelled = false;
        async function load() {
            setLoading(true);
            setError("");
            try {
                const data = await fetchApi<Annotation[]>(`/api/annotations/${encodeURIComponent(nodeId)}`);
                if (!cancelled) setAnnotations(data);
            } catch {
                if (!cancelled) setError("批注加载失败");
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        load();
        return () => { cancelled = true; };
    }, [nodeId]);

    async function handleSubmit() {
        if (!draft.trim() || submitting) return;
        setSubmitting(true);
        setError("");
        try {
            const ann = await fetchApi<Annotation>("/api/annotations", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ node_id: nodeId, node_type: nodeType, content: draft.trim() }),
            });
            setAnnotations(prev => [...prev, ann]);
            setDraft("");
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "提交失败");
        } finally {
            setSubmitting(false);
        }
    }

    async function handleDelete(id: number) {
        try {
            await fetchApi(`/api/annotations/${id}`, { method: "DELETE" });
            setAnnotations(prev => prev.filter(a => a.id !== id));
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : "删除失败");
        }
    }

    return (
        <div className="px-4 py-3 flex flex-col gap-2 flex-1">
            <div className="flex items-center gap-1.5 text-xs text-gray-400 font-medium">
                <MessageSquarePlus size={13} />
                现场批注
                {annotations.length > 0 && <span className="ml-auto text-gray-600">{annotations.length} 条</span>}
            </div>

            {loading && <div className="flex justify-center py-4"><Loader2 size={16} className="animate-spin text-gray-600" /></div>}
            {!loading && annotations.length === 0 && <p className="text-[11px] text-gray-600 text-center py-2">暂无批注</p>}

            {!loading && annotations.map(a => (
                <div key={a.id} className="bg-gray-800/60 rounded-lg px-3 py-2 text-xs group relative">
                    <div className="flex items-center gap-1.5 text-gray-500 mb-1">
                        <span className="text-indigo-400 font-medium">{a.full_name}</span>
                        <span>·</span>
                        <span>{new Date(a.created_at).toLocaleDateString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                    </div>
                    <p className="text-gray-300 leading-relaxed whitespace-pre-wrap">{a.content}</p>
                    {(a.user_id === currentUserId || isAdmin) && (
                        <button onClick={() => handleDelete(a.id)}
                            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded text-gray-600 hover:text-red-400 transition-all"
                            title="删除批注">
                            <Trash2 size={11} />
                        </button>
                    )}
                </div>
            ))}

            {error && <p className="text-[11px] text-red-400 text-center">{error}</p>}

            <div className="mt-auto pt-2">
                <textarea ref={textareaRef} value={draft} onChange={e => setDraft(e.target.value)}
                    onKeyDown={e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit(); }}
                    placeholder="添加现场心得或纠错备注… (Ctrl+Enter 提交)"
                    rows={3}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-200 placeholder-gray-600 outline-none focus:border-indigo-500 resize-none leading-relaxed"
                />
                <button onClick={handleSubmit} disabled={!draft.trim() || submitting}
                    className="mt-1.5 w-full py-1.5 rounded-lg text-xs font-medium transition-colors bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-40 disabled:cursor-not-allowed">
                    {submitting ? "提交中…" : "提交批注"}
                </button>
            </div>
        </div>
    );
}
