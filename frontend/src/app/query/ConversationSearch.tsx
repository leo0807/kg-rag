"use client";

import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";

interface SearchResult {
  id: string;
  title: string;
  highlight: string;
  matched_messages: { role: string; snippet: string }[];
  is_pinned: boolean;
  tags: string[];
  created_at: string;
}

interface Props {
  onSelect: (id: string) => void;
  onClose: () => void;
}

export function ConversationSearch({ onSelect, onClose }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  useEffect(() => {
    if (!q.trim()) { setResults([]); return; }
    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await fetchApi<{ conversations: SearchResult[] }>(
          `/api/conversations/search?q=${encodeURIComponent(q)}&limit=15`
        );
        setResults(data.conversations);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div className="fixed inset-0 bg-black/70 flex items-start justify-center pt-24 z-50"
      onClick={onClose}>
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-[480px] max-w-[92vw] shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}>
        {/* Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800">
          <Search size={15} className="text-gray-500 shrink-0" />
          <input ref={inputRef} value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索对话内容、标题…"
            className="flex-1 bg-transparent text-gray-200 text-sm outline-none placeholder-gray-600" />
          {loading && <span className="text-[10px] text-gray-600">搜索中…</span>}
          <button onClick={onClose} className="text-gray-600 hover:text-gray-300"><X size={14} /></button>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-auto">
          {!q.trim() && (
            <p className="text-xs text-gray-600 text-center py-8">输入关键词搜索历史对话</p>
          )}
          {q.trim() && results.length === 0 && !loading && (
            <p className="text-xs text-gray-600 text-center py-8">无匹配结果</p>
          )}
          {results.map((r) => (
            <button key={r.id} type="button"
              onClick={() => { onSelect(r.id); onClose(); }}
              className="w-full text-left px-4 py-3 border-b border-gray-800/50
                         hover:bg-gray-800 transition-colors">
              <div className="text-xs font-medium text-gray-200 truncate">{r.title}</div>
              {r.highlight && r.highlight !== r.title && (
                <div className="text-[11px] text-gray-500 mt-0.5 line-clamp-2"
                  dangerouslySetInnerHTML={{ __html: r.highlight }} />
              )}
              <div className="text-[10px] text-gray-600 mt-1">
                {new Date(r.created_at).toLocaleDateString("zh-CN")}
                {r.is_pinned && <span className="ml-2 text-amber-600">置顶</span>}
                {r.tags.length > 0 && (
                  <span className="ml-2">#{r.tags.join(" #")}</span>
                )}
              </div>
            </button>
          ))}
        </div>

        <div className="px-4 py-2 text-[10px] text-gray-700 border-t border-gray-800">
          ↵ 选择 · Esc 关闭
        </div>
      </div>
    </div>
  );
}
