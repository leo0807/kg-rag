"use client";

import { CircleDot, FileText, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { GraphNode } from "./constants";

export interface SearchDocumentResult {
  doc_id: string;
  title: string;
}

interface Props {
  searchQuery: string;
  handleSearch: (q: string) => void;
  searchNodeResults: GraphNode[];
  searchDocResults: SearchDocumentResult[];
  onSelectNodeResult: (node: GraphNode) => void;
  onSelectDocumentResult: (doc: SearchDocumentResult) => void;
}

export function GraphToolbarSearch({
  searchQuery,
  handleSearch,
  searchNodeResults,
  searchDocResults,
  onSelectNodeResult,
  onSelectDocumentResult,
}: Props) {
  const searchRef = useRef<HTMLInputElement | null>(null);
  const [searchFocused, setSearchFocused] = useState(false);
  const [searchBoxRect, setSearchBoxRect] = useState<DOMRect | null>(null);
  const showSearchDropdown = searchFocused && searchQuery.trim().length > 0;
  const hasSearchResults =
    searchNodeResults.length > 0 || searchDocResults.length > 0;

  useEffect(() => {
    if (!searchFocused) return;
    const updateRect = () => {
      if (searchRef.current) {
        setSearchBoxRect(searchRef.current.getBoundingClientRect());
      }
    };
    updateRect();
    window.addEventListener("resize", updateRect);
    window.addEventListener("scroll", updateRect, true);
    return () => {
      window.removeEventListener("resize", updateRect);
      window.removeEventListener("scroll", updateRect, true);
    };
  }, [searchFocused]);

  const dropdown =
    showSearchDropdown && searchBoxRect && typeof document !== "undefined"
      ? createPortal(
          <div
            className="fixed max-h-60 overflow-y-auto rounded-b-lg border border-gray-700 bg-gray-900 shadow-xl"
            style={{
              top: searchBoxRect.bottom + 4,
              left: searchBoxRect.left,
              width: searchBoxRect.width,
              zIndex: 9999,
            }}
          >
            {searchNodeResults.length > 0 && (
              <div className="border-b border-gray-800/80 px-2 py-2">
                <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-gray-500">
                  节点
                </div>
                <div className="space-y-1">
                  {searchNodeResults.map((node) => (
                    <button
                      key={node.id}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        onSelectNodeResult(node);
                        setSearchFocused(false);
                      }}
                      className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-gray-800"
                    >
                      <CircleDot
                        size={13}
                        className="mt-0.5 shrink-0 text-indigo-400"
                      />
                      <div className="min-w-0">
                        <div className="truncate text-xs font-medium text-gray-100">
                          {node.name || node.id}
                        </div>
                        <div className="truncate text-[11px] text-gray-500">
                          {node.type || node.label || "节点"}
                          {node.doc_id ? ` · ${node.doc_id}` : ""}
                          {node.number ? ` · §${node.number}` : ""}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {searchDocResults.length > 0 && (
              <div className="px-2 py-2">
                <div className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-gray-500">
                  文档
                </div>
                <div className="space-y-1">
                  {searchDocResults.map((doc) => (
                    <button
                      key={doc.doc_id}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        onSelectDocumentResult(doc);
                        setSearchFocused(false);
                      }}
                      className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-gray-800"
                    >
                      <FileText
                        size={13}
                        className="mt-0.5 shrink-0 text-emerald-400"
                      />
                      <div className="min-w-0">
                        <div className="truncate text-xs font-medium text-gray-100">
                          {doc.doc_id}
                        </div>
                        <div className="truncate text-[11px] text-gray-500">
                          {doc.title || "未命名文档"}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
            {!hasSearchResults && (
              <div className="px-3 py-2 text-xs text-gray-500">
                没有匹配的节点或文档
              </div>
            )}
          </div>,
          document.body,
        )
      : null;

  return (
    <div className="relative z-[210] shrink-0">
      <Search
        size={12}
        className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-gray-500"
      />
      <input
        ref={searchRef}
        value={searchQuery}
        onChange={(e) => handleSearch(e.target.value)}
        onFocus={() => setSearchFocused(true)}
        onBlur={() => window.setTimeout(() => setSearchFocused(false), 120)}
        placeholder="搜索规范编号..."
        className="h-7 w-52 shrink-0 rounded border border-gray-700 bg-gray-800 pl-6 pr-2 text-xs text-gray-200 outline-none focus:border-indigo-500"
      />
      {dropdown}
    </div>
  );
}
