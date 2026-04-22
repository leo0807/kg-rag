"use client";

import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  Download,
  FileText,
  Loader2,
  Star,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import type { MouseEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useFavorites } from "@/app/favorites/useFavorites";
import { fetchApi } from "@/lib/api";
import { DrawingsTab } from "./DrawingsTab";
import PdfPanel from "./PdfPanel";
import { ReprocessPanel } from "./ReprocessPanel";

interface UserInfo {
  username: string;
  full_name: string;
  department: string;
  is_admin?: boolean;
}

/** 从 localStorage 读取当前用户信息 */
function getCurrentUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** 生成重复水印的 SVG data-URI（每块 280×140，旋转 -30°） */
function buildWatermarkUrl(name: string, time: string): string {
  const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="280" height="140">
  <g transform="rotate(-30 140 70)" opacity="0.13" fill="#94a3b8"
     font-family="PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif" text-anchor="middle">
    <text x="140" y="58"  font-size="15" font-weight="600">${name}</text>
    <text x="140" y="82"  font-size="11">${time}</text>
  </g>
</svg>`.trim();
  return `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}")`;
}

interface Section {
  number: string;
  title: string;
  chunk_id: string;
  page_idx?: number | null;
  bbox?: [number, number, number, number] | number[] | null;
}

interface DocumentDetail {
  doc_id: string;
  title: string;
  version: string;
  issue_date: string;
  sections: Section[];
  refs: string[];
}

interface SectionContent {
  number: string;
  title: string;
  content: string;
}

type IdleDeadlineLike = {
  didTimeout: boolean;
  timeRemaining: () => number;
};

type IdleWindow = Window & {
  requestIdleCallback?: (
    callback: (deadline: IdleDeadlineLike) => void,
    options?: { timeout: number },
  ) => number;
  cancelIdleCallback?: (handle: number) => void;
};

function sortSections(sections: Section[]): Section[] {
  return [...sections].sort((a, b) => {
    const aParts = a.number.split(".").map((p) => parseInt(p, 10) || 0);
    const bParts = b.number.split(".").map((p) => parseInt(p, 10) || 0);
    for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
      const diff = (aParts[i] ?? 0) - (bParts[i] ?? 0);
      if (diff !== 0) return diff;
    }
    return 0;
  });
}

function highlight(text: string, keyword: string) {
  if (!keyword) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(keyword.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-indigo-500/30 text-indigo-300 rounded px-0.5">
        {text.slice(idx, idx + keyword.length)}
      </mark>
      {text.slice(idx + keyword.length)}
    </>
  );
}

export default function DocumentDetailClient({ docId }: { docId: string }) {
  const searchParams = useSearchParams();
  const initialPage = searchParams.get("page");

  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);
  const [activeChunk, setActiveChunk] = useState<string | null>(null);
  const [sectionContent, setSectionContent] = useState<
    Record<string, SectionContent>
  >({});
  const [loadingChunk, setLoadingChunk] = useState<string | null>(null);
  const [sectionSearch, setSectionSearch] = useState("");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [showPdf, setShowPdf] = useState(initialPage !== null);
  const [anchorPage, setAnchorPage] = useState<number | undefined>(
    initialPage ? parseInt(initialPage, 10) : undefined,
  );
  const [watermarkUrl, setWatermarkUrl] = useState("");
  const [activeTab, setActiveTab] = useState<
    "sections" | "drawings" | "reprocess"
  >("sections");
  const [visibleSectionIds, setVisibleSectionIds] = useState<string[]>([]);
  const sectionRequestsRef = useRef(new Map<string, Promise<void>>());
  const sectionContentRef = useRef<Record<string, SectionContent>>({});
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const sectionRowRefs = useRef(new Map<string, HTMLDivElement>());
  const visibleSectionIdsRef = useRef(new Set<string>());
  const idlePrefetchHandleRef = useRef<number | null>(null);
  const prefetchingChunkRef = useRef<string | null>(null);
  const { getFavoriteId, addFavorite, removeFavorite } = useFavorites();
  const sortedSections = useMemo(
    () => sortSections(doc?.sections ?? []),
    [doc?.sections],
  );
  const activeSection = useMemo(() => {
    if (!activeChunk) return undefined;
    return sortedSections.find((section) => section.chunk_id === activeChunk);
  }, [activeChunk, sortedSections]);
  const activeSectionLabel = useMemo(
    () =>
      activeSection
        ? `§${activeSection.number} ${activeSection.title}`
        : undefined,
    [activeSection],
  );
  const clearActiveSectionSelection = useCallback(() => {
    setActiveChunk(null);
    setAnchorPage(undefined);
  }, []);

  useEffect(() => {
    sectionContentRef.current = sectionContent;
  }, [sectionContent]);

  // 监控 URL 参数变化
  useEffect(() => {
    const page = searchParams.get("page");
    if (page !== null) {
      const p = parseInt(page, 10);
      setAnchorPage(p);
      setShowPdf(true);
    }
  }, [searchParams]);

  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash === "drawings" || hash === "reprocess") setActiveTab(hash);
  }, []);

  const refresh = useCallback(() => {
    if (!docId) return;
    fetchApi<DocumentDetail>(`/api/documents/${docId}`)
      .then(setDoc)
      .catch(() => {});
  }, [docId]);

  useEffect(() => {
    if (!doc?.sections?.length) return;
    if (anchorPage === undefined || Number.isNaN(anchorPage)) return;

    if (
      activeSection &&
      typeof activeSection.page_idx === "number" &&
      activeSection.page_idx === anchorPage
    ) {
      return;
    }

    const byPage = [...sortedSections]
      .filter(
        (section): section is Section & { page_idx: number } =>
          typeof section.page_idx === "number",
      )
      .sort((a, b) => a.page_idx - b.page_idx);

    if (byPage.length === 0) return;

    const samePageSections = byPage.filter(
      (section) => section.page_idx === anchorPage,
    );
    const current =
      samePageSections[0] ??
      byPage.reduce<Section | null>((best, section) => {
        if (section.page_idx > anchorPage) return best;
        if (!best) return section;
        return section.page_idx >= (best.page_idx ?? -1) ? section : best;
      }, null);

    if (current) {
      setActiveChunk((prev) =>
        prev === current.chunk_id ? prev : current.chunk_id,
      );
    }
  }, [activeSection, anchorPage, doc?.sections, sortedSections]);

  useEffect(() => {
    if (!docId) return;
    refresh();

    // 尝试获取 PDF 静态地址（文件不存在时静默失败）
    fetchApi<{
      preview_url: string;
      download_url: string;
      type?: string;
      filename?: string;
    }>(`/api/documents/${docId}/pdf-url`)
      .then((data) => {
        const token = localStorage.getItem("token") ?? "";
        setDownloadUrl(data.download_url);
        setFileName(data.filename || "");
        // All formats: server-side PDF preview (LibreOffice converts DOC/DOCX)
        const preview = `${data.preview_url}?token=${encodeURIComponent(token)}&t=${Date.now()}`;
        setPdfUrl(preview);
      })
      .catch(() => {});

    // 构建水印（用户名 + 当前时间）
    const user = getCurrentUser();
    const name = user?.full_name || user?.username || "未知用户";
    setIsAdmin(Boolean(user?.is_admin));
    const time = new Date().toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
    setWatermarkUrl(buildWatermarkUrl(name, time));
  }, [docId, refresh]);

  async function handleDownload() {
    if (!downloadUrl) return;
    const token = localStorage.getItem("token") ?? "";
    if (!token) return;
    const res = await fetch(downloadUrl, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = fileName || `${docId}.bin`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function toggleSectionFavorite(
    e: MouseEvent,
    section: { chunk_id: string; title: string; number: string },
  ) {
    e.stopPropagation();
    const favId = getFavoriteId({
      type: "section",
      section_id: section.chunk_id,
    });
    if (favId) {
      await removeFavorite(favId);
    } else {
      await addFavorite({
        type: "section",
        doc_id: docId,
        section_id: section.chunk_id,
        title: `§${section.number} ${section.title}`,
      });
    }
  }

  const activateSection = useCallback(
    (section: Section) => {
      setActiveChunk(section.chunk_id);
      if (pdfUrl) {
        setShowPdf(true);
        if (typeof section.page_idx === "number") {
          setAnchorPage(section.page_idx);
        } else {
          setAnchorPage(undefined);
        }
      }
    },
    [pdfUrl],
  );

  const ensureSectionContent = useCallback(
    async (section: Section, options?: { background?: boolean }) => {
      if (sectionContentRef.current[section.chunk_id]) return;

      const existing = sectionRequestsRef.current.get(section.chunk_id);
      if (existing) {
        await existing;
        return;
      }

      if (!options?.background) {
        setLoadingChunk(section.chunk_id);
      }
      const request = fetchApi<SectionContent>(
        `/api/sections/${section.chunk_id}`,
      )
        .then((data) => {
          setSectionContent((prev) => ({ ...prev, [section.chunk_id]: data }));
        })
        .finally(() => {
          sectionRequestsRef.current.delete(section.chunk_id);
          if (!options?.background) {
            setLoadingChunk((prev) =>
              prev === section.chunk_id ? null : prev,
            );
          }
        });

      sectionRequestsRef.current.set(section.chunk_id, request);
      await request;
    },
    [],
  );

  async function toggleSectionExpand(section: Section) {
    activateSection(section);
    if (expandedChunk === section.chunk_id) {
      setExpandedChunk(null);
      return;
    }

    setExpandedChunk(section.chunk_id);
    await ensureSectionContent(section);
  }

  function handleSectionNavigate(section: Section) {
    activateSection(section);
  }

  const visibleSections = sectionSearch
    ? sortedSections.filter(
        (s) =>
          s.title.toLowerCase().includes(sectionSearch.toLowerCase()) ||
          s.number.includes(sectionSearch),
      )
    : sortedSections;

  useEffect(() => {
    if (!doc) return;
    if (activeTab !== "sections") {
      visibleSectionIdsRef.current.clear();
      setVisibleSectionIds([]);
      return;
    }

    const root = scrollContainerRef.current;
    if (!root) return;

    const observer = new IntersectionObserver(
      (entries) => {
        let changed = false;
        const next = new Set(visibleSectionIdsRef.current);

        for (const entry of entries) {
          const chunkId = (entry.target as HTMLElement).dataset.chunkId;
          if (!chunkId) continue;
          if (entry.isIntersecting) {
            if (!next.has(chunkId)) {
              next.add(chunkId);
              changed = true;
            }
          } else if (next.delete(chunkId)) {
            changed = true;
          }
        }

        if (!changed) return;
        visibleSectionIdsRef.current = next;
        const orderedVisible = visibleSections
          .filter((section) => next.has(section.chunk_id))
          .map((section) => section.chunk_id);

        setVisibleSectionIds((prev) => {
          if (
            prev.length === orderedVisible.length &&
            prev.every((value, index) => value === orderedVisible[index])
          ) {
            return prev;
          }
          return orderedVisible;
        });
      },
      {
        root,
        rootMargin: "140px 0px",
        threshold: 0.01,
      },
    );

    for (const section of visibleSections) {
      const node = sectionRowRefs.current.get(section.chunk_id);
      if (node) observer.observe(node);
    }

    return () => {
      observer.disconnect();
    };
  }, [activeTab, visibleSections, doc]);

  useEffect(() => {
    if (!doc) return;
    if (activeTab !== "sections" || visibleSectionIds.length === 0) return;
    if (prefetchingChunkRef.current) return;

    const prefetchQueue = visibleSections.filter(
      (section) =>
        visibleSectionIds.includes(section.chunk_id) &&
        !sectionContentRef.current[section.chunk_id] &&
        !sectionRequestsRef.current.has(section.chunk_id) &&
        section.chunk_id !== expandedChunk,
    );

    const nextSection = prefetchQueue[0];
    if (!nextSection) return;

    let cancelled = false;
    const idleWindow = window as IdleWindow;

    const runPrefetch = async (deadline: IdleDeadlineLike) => {
      if (cancelled) return;
      if (!deadline.didTimeout && deadline.timeRemaining() < 8) {
        schedulePrefetch();
        return;
      }

      prefetchingChunkRef.current = nextSection.chunk_id;
      try {
        await ensureSectionContent(nextSection, { background: true });
      } finally {
        prefetchingChunkRef.current = null;
        idlePrefetchHandleRef.current = null;
      }
    };

    const schedulePrefetch = () => {
      if (cancelled || idlePrefetchHandleRef.current !== null) return;

      if (idleWindow.requestIdleCallback) {
        idlePrefetchHandleRef.current = idleWindow.requestIdleCallback(
          (deadline) => {
            idlePrefetchHandleRef.current = null;
            void runPrefetch(deadline);
          },
          { timeout: 1200 },
        );
      } else {
        idlePrefetchHandleRef.current = window.setTimeout(() => {
          idlePrefetchHandleRef.current = null;
          void runPrefetch({
            didTimeout: true,
            timeRemaining: () => 0,
          });
        }, 180);
      }
    };

    schedulePrefetch();

    return () => {
      cancelled = true;
      if (idlePrefetchHandleRef.current !== null) {
        if (idleWindow.cancelIdleCallback) {
          idleWindow.cancelIdleCallback(idlePrefetchHandleRef.current);
        } else {
          window.clearTimeout(idlePrefetchHandleRef.current);
        }
        idlePrefetchHandleRef.current = null;
      }
    };
  }, [
    activeTab,
    ensureSectionContent,
    expandedChunk,
    visibleSectionIds,
    visibleSections,
    doc,
  ]);

  if (!doc) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500 text-sm gap-2">
        <Loader2 size={16} className="animate-spin" />
        加载中...
      </div>
    );
  }

  const docPanel = (
    <div
      ref={scrollContainerRef}
      className={`bg-gray-950 overflow-y-auto ${showPdf ? "flex-1 min-w-0" : "p-8 max-w-3xl min-h-screen"}`}
    >
      <div className={showPdf ? "px-6 pt-5 pb-4" : "mb-6"}>
        <a
          href="/library"
          className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          <ArrowLeft size={14} />
          返回文档库
        </a>
      </div>

      {/* 标题区 */}
      <div className={showPdf ? "px-6 pb-4 border-b border-gray-800" : "mb-8"}>
        <div className="text-sm font-mono text-indigo-400 mb-1">
          {doc.doc_id} · 版本 {doc.version || "—"}
        </div>
        <h1 className="text-xl font-semibold text-white leading-snug">
          {doc.title || "未命名文档"}
        </h1>
        <div className="text-sm text-gray-500 mt-1">
          发布日期：{doc.issue_date || "—"}
        </div>

        {/* 操作按钮行 */}
        <div className="flex items-center gap-2 mt-3">
          {pdfUrl ? (
            <button
              type="button"
              onClick={() => setShowPdf((v) => !v)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                showPdf
                  ? "bg-indigo-600 text-white hover:bg-indigo-700"
                  : "bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white border border-gray-700"
              }`}
            >
              <FileText size={13} />
              {showPdf ? "关闭预览" : "预览原文"}
            </button>
          ) : (
            <span
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                                         text-gray-600 border border-gray-800 cursor-default"
              title="文件未找到"
            >
              <FileText size={13} />
              原文仅支持下载
            </span>
          )}
          {isAdmin && downloadUrl && (
            <button
              type="button"
              onClick={handleDownload}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                                       bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700
                                       border border-gray-700 transition-colors"
            >
              <Download size={13} />
              下载原文
            </button>
          )}
        </div>
      </div>

      {doc.refs.length > 0 && (
        <div
          className={showPdf ? "px-6 py-4 border-b border-gray-800" : "mb-8"}
        >
          <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">
            引用文件
          </div>
          <div className="flex flex-wrap gap-2">
            {doc.refs.map((ref) => (
              <a
                key={ref}
                href={`/library/${ref}`}
                className="px-3 py-1 bg-gray-900 border border-gray-700 rounded-md
                                           text-sm font-mono text-indigo-400 hover:border-indigo-500 transition-colors"
              >
                {ref}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* 选项卡：章节 / 图纸 */}
      <div className={showPdf ? "px-6 pt-3" : "mt-2"}>
        <div className="flex items-center gap-1 border-b border-gray-800 mb-4">
          {(
            [
              ["sections", `章节目录 (${doc.sections.length})`],
              ["drawings", "工程图纸"],
              ["reprocess", "重新处理"],
            ] as const
          ).map(([tab, label]) => (
            <button
              key={tab}
              type="button"
              onClick={() => {
                setActiveTab(tab as "sections" | "drawings" | "reprocess");
                history.replaceState(
                  null,
                  "",
                  tab === "sections"
                    ? window.location.pathname + window.location.search
                    : `${window.location.pathname}${window.location.search}#${tab}`,
                );
              }}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${activeTab === tab ? "border-indigo-500 text-white" : "border-transparent text-gray-500 hover:text-gray-300"}`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 章节列表 */}
        {activeTab === "sections" && (
          <>
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs text-gray-500">
                {sectionSearch && `匹配 ${visibleSections.length} 个`}
              </div>
              <input
                value={sectionSearch}
                onChange={(e) => setSectionSearch(e.target.value)}
                placeholder="搜索章节..."
                className="px-2.5 py-1 bg-gray-900 border border-gray-700 rounded
                                           text-xs text-gray-200 outline-none focus:border-indigo-500
                                           placeholder-gray-500 w-36"
              />
            </div>
            <div className="space-y-0.5">
              {visibleSections.map((section) => {
                const isExpanded = expandedChunk === section.chunk_id;
                const isLoading = loadingChunk === section.chunk_id;
                const isActive = activeChunk === section.chunk_id;
                const content = sectionContent[section.chunk_id];
                return (
                  <div
                    key={section.chunk_id}
                    ref={(node) => {
                      if (node) {
                        sectionRowRefs.current.set(section.chunk_id, node);
                      } else {
                        sectionRowRefs.current.delete(section.chunk_id);
                      }
                    }}
                    data-chunk-id={section.chunk_id}
                  >
                    <div
                      className={`flex items-center group rounded-lg border transition-colors ${
                        isActive
                          ? "bg-gray-900 border-indigo-500/70 shadow-[0_0_0_1px_rgba(99,102,241,0.35)]"
                          : "border-transparent hover:bg-gray-900"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => handleSectionNavigate(section)}
                        className="flex-1 flex items-baseline gap-3 px-3 py-2.5 text-left min-w-0"
                        aria-current={isActive ? "true" : undefined}
                      >
                        <span
                          className={`text-xs font-mono w-12 shrink-0 ${isActive ? "text-indigo-300" : "text-gray-500"}`}
                        >
                          {section.number}
                        </span>
                        <span
                          className={`text-sm flex-1 min-w-0 ${isActive ? "text-white" : "text-gray-300"}`}
                        >
                          {highlight(section.title, sectionSearch)}
                        </span>
                        <span
                          className={`shrink-0 ${isActive ? "text-indigo-300" : "text-gray-600 opacity-0 group-hover:opacity-100"}`}
                        >
                          {typeof section.page_idx === "number"
                            ? `P${section.page_idx + 1}`
                            : ""}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() => void toggleSectionExpand(section)}
                        title={isExpanded ? "收起章节内容" : "展开章节内容"}
                        className={`px-2 py-2.5 shrink-0 transition-colors ${
                          isActive
                            ? "text-indigo-300 hover:text-white"
                            : "text-gray-600 hover:text-gray-300"
                        }`}
                      >
                        {isLoading ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : isExpanded ? (
                          <ChevronUp size={12} />
                        ) : (
                          <ChevronDown size={12} />
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={(e) => toggleSectionFavorite(e, section)}
                        title={
                          getFavoriteId({
                            type: "section",
                            section_id: section.chunk_id,
                          })
                            ? "取消收藏"
                            : "收藏此章节"
                        }
                        className="px-2 py-2.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <Star
                          size={13}
                          className={
                            getFavoriteId({
                              type: "section",
                              section_id: section.chunk_id,
                            })
                              ? "text-amber-400 fill-amber-400"
                              : "text-gray-600 hover:text-amber-400"
                          }
                        />
                      </button>
                    </div>
                    {isExpanded && (
                      <div className="mx-3 mb-2 px-4 py-3 bg-gray-900 rounded-lg border border-gray-800 text-sm text-gray-400 leading-relaxed whitespace-pre-wrap">
                        {content ? (
                          content.content
                        ) : (
                          <div className="flex items-center gap-2 text-gray-500">
                            <Loader2 size={14} className="animate-spin" />
                            正在加载章节内容...
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}

        {activeTab === "drawings" && <DrawingsTab docId={docId} />}
        {activeTab === "reprocess" && (
          <ReprocessPanel docId={docId} onComplete={refresh} />
        )}
      </div>
    </div>
  );

  // ── 整体布局 ─────────────────────────────────────────────────────────────
  if (showPdf && pdfUrl) {
    return (
      <div className="flex h-full overflow-hidden">
        <div className="flex flex-col overflow-hidden" style={{ width: "42%" }}>
          {docPanel}
        </div>
        <PdfPanel
          docId={doc.doc_id}
          pdfUrl={pdfUrl}
          watermarkUrl={watermarkUrl}
          canDownload={isAdmin && Boolean(downloadUrl)}
          anchorPage={anchorPage}
          anchorBBox={
            activeSection && typeof activeSection.page_idx === "number"
              ? (activeSection.bbox ?? undefined)
              : undefined
          }
          activeSectionNumber={activeSection?.number}
          activeSectionTitle={activeSection?.title}
          activeSectionLabel={activeSectionLabel}
          onManualPageChange={clearActiveSectionSelection}
          onDownload={handleDownload}
          onClose={() => setShowPdf(false)}
        />
      </div>
    );
  }

  return docPanel;
}
