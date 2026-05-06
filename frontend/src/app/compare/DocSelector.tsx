"use client";
import { useState, useEffect, useMemo, useRef } from "react";
import { ChevronDown, Check } from "lucide-react";

export interface Document { doc_id: string; title: string; version: string; sections: number; }

export function DocSelector({ docs, selectedId, onSelect, label }: {
    docs: Document[]; selectedId: string; onSelect: (id: string) => void; label: string;
}) {
    const [open, setOpen] = useState(false);
    const [search, setSearch] = useState("");
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
        };
        document.addEventListener("mousedown", handleClick);
        return () => document.removeEventListener("mousedown", handleClick);
    }, []);

    const filtered = useMemo(() =>
        docs.filter(d => d.doc_id.toLowerCase().includes(search.toLowerCase()) || d.title.toLowerCase().includes(search.toLowerCase())),
        [docs, search]
    );
    const selectedDoc = docs.find(d => d.doc_id === selectedId);

    return (
        <div className="flex-1 min-w-[200px]" ref={containerRef}>
            <label className="text-xs text-gray-500 mb-1 block">{label}</label>
            <div className="relative">
                <button onClick={() => setOpen(!open)}
                    className="w-full flex items-center justify-between px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-200 outline-none focus:border-indigo-500">
                    <span className="truncate">{selectedDoc ? `${selectedDoc.doc_id} ${selectedDoc.title}` : "选择文档..."}</span>
                    <ChevronDown size={14} className="text-gray-500" />
                </button>
                {open && (
                    <div className="absolute z-20 top-full mt-1 w-full bg-gray-900 border border-gray-700 rounded-lg shadow-xl py-1">
                        <div className="px-2 pb-1">
                            <input autoFocus value={search} onChange={e => setSearch(e.target.value)}
                                placeholder="搜索文档..."
                                className="w-full px-2 py-1.5 bg-gray-950 border border-gray-800 rounded text-xs text-white placeholder-gray-600 outline-none" />
                        </div>
                        <div className="max-h-60 overflow-y-auto">
                            {filtered.map(d => (
                                <button key={d.doc_id} onClick={() => { onSelect(d.doc_id); setOpen(false); }}
                                    className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800 flex items-center gap-2">
                                    {selectedId === d.doc_id && <Check size={12} className="text-indigo-500" />}
                                    <span className={selectedId === d.doc_id ? "ml-0" : "ml-5"}>{d.doc_id} - {d.title}</span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
