"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { MouseEvent } from "react";
import { useFavorites } from "@/app/favorites/useFavorites";
import { fetchApi } from "@/lib/api";

export interface Section {
  number: string;
  title: string;
  chunk_id: string;
  page_idx?: number | null;
  bbox?: [number, number, number, number] | number[] | null;
}

export interface DocumentDetail {
  doc_id: string;
  title: string;
  version: string;
  issue_date: string;
  sections: Section[];
  refs: string[];
}

export interface SectionContent {
  number: string;
  title: string;
  content: string;
}

interface UserInfo {
  username: string;
  full_name: string;
  department: string;
  is_admin?: boolean;
}

function getCurrentUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

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

export function useDocDetail(docId: string) {
  const searchParams = useSearchParams();
  const initialPage = searchParams.get("page");

  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [expandedChunk, setExpandedChunk] = useState<string | null>(null);
  const [activeChunk, setActiveChunk] = useState<string | null>(null);
  const [sectionContent, setSectionContent] = useState<Record<string, SectionContent>>({});
  const [loadingChunk, setLoadingChunk] = useState<string | null>(null);
  const [sectionSearch, setSectionSearch] = useState("");
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string>("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [showPdf, setShowPdf] = useState(initialPage !== null || searchParams.get("preview") === "true");
  const [anchorPage, setAnchorPage] = useState<number | undefined>(
    initialPage ? parseInt(initialPage, 10) : undefined,
  );
  const [watermarkUrl, setWatermarkUrl] = useState("");
  const initialTab = (searchParams.get("tab") as "sections" | "drawings" | "reprocess" | null) ?? "sections";
  const [activeTab, setActiveTab] = useState<"sections" | "drawings" | "reprocess">(
    initialTab === "drawings" || initialTab === "reprocess" ? initialTab : "sections",
  );

  const sectionRequestsRef = useRef(new Map<string, Promise<void>>());
  const sectionContentRef = useRef<Record<string, SectionContent>>({});

  const { getFavoriteId, addFavorite, removeFavorite } = useFavorites();

  const sortedSections = useMemo(() => sortSections(doc?.sections ?? []), [doc?.sections]);

  const activeSection = useMemo(() => {
    if (!activeChunk) return undefined;
    return sortedSections.find((s) => s.chunk_id === activeChunk);
  }, [activeChunk, sortedSections]);

  const activeSectionLabel = useMemo(
    () => (activeSection ? `§${activeSection.number} ${activeSection.title}` : undefined),
    [activeSection],
  );

  const visibleSections = sectionSearch
    ? sortedSections.filter(
        (s) =>
          s.title.toLowerCase().includes(sectionSearch.toLowerCase()) ||
          s.number.includes(sectionSearch),
      )
    : sortedSections;

  const clearActiveSectionSelection = useCallback(() => {
    setActiveChunk(null);
    setAnchorPage(undefined);
  }, []);

  useEffect(() => { sectionContentRef.current = sectionContent; }, [sectionContent]);

  useEffect(() => {
    const page = searchParams.get("page");
    if (page !== null) { setAnchorPage(parseInt(page, 10)); setShowPdf(true); }
    if (searchParams.get("preview") === "true") setShowPdf(true);
  }, [searchParams]);

  useEffect(() => {
    const hash = window.location.hash.slice(1);
    if (hash === "drawings" || hash === "reprocess") setActiveTab(hash);
  }, []);

  const refresh = useCallback(() => {
    if (!docId) return;
    fetchApi<DocumentDetail>(`/api/documents/${docId}`).then(setDoc).catch(() => {});
  }, [docId]);

  useEffect(() => {
    if (!doc?.sections?.length || anchorPage === undefined || Number.isNaN(anchorPage)) return;
    if (activeSection && typeof activeSection.page_idx === "number" && activeSection.page_idx === anchorPage) return;
    const byPage = [...sortedSections]
      .filter((s): s is Section & { page_idx: number } => typeof s.page_idx === "number")
      .sort((a, b) => a.page_idx - b.page_idx);
    if (!byPage.length) return;
    const samePageSections = byPage.filter((s) => s.page_idx === anchorPage);
    const current =
      samePageSections[0] ??
      byPage.reduce<Section | null>((best, s) => {
        if (s.page_idx > anchorPage) return best;
        return !best ? s : s.page_idx >= (best.page_idx ?? -1) ? s : best;
      }, null);
    if (current) setActiveChunk((prev) => (prev === current.chunk_id ? prev : current.chunk_id));
  }, [activeSection, anchorPage, doc?.sections, sortedSections]);

  useEffect(() => {
    if (!docId) return;
    refresh();
    fetchApi<{ preview_url: string; download_url: string; type?: string; filename?: string }>(
      `/api/documents/${docId}/pdf-url`,
    )
      .then((data) => {
        const token = localStorage.getItem("token") ?? "";
        setDownloadUrl(data.download_url);
        setFileName(data.filename || "");
        const preview = `${data.preview_url}?token=${encodeURIComponent(token)}&t=${Date.now()}`;
        setPdfUrl(preview);
      })
      .catch(() => {});
    const user = getCurrentUser();
    const name = user?.full_name || user?.username || "未知用户";
    setIsAdmin(Boolean(user?.is_admin));
    const time = new Date().toLocaleString("zh-CN", {
      year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    });
    setWatermarkUrl(buildWatermarkUrl(name, time));
  }, [docId, refresh]);

  async function handleDownload() {
    if (!downloadUrl) return;
    const token = localStorage.getItem("token") ?? "";
    if (!token) return;
    const res = await fetch(downloadUrl, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) return;
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = fileName || `${docId}.bin`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function toggleSectionFavorite(e: MouseEvent, section: { chunk_id: string; title: string; number: string }) {
    e.stopPropagation();
    const favId = getFavoriteId({ type: "section", section_id: section.chunk_id });
    if (favId) {
      await removeFavorite(favId);
    } else {
      await addFavorite({ type: "section", doc_id: docId, section_id: section.chunk_id, title: `§${section.number} ${section.title}` });
    }
  }

  const activateSection = useCallback(
    (section: Section) => {
      setActiveChunk(section.chunk_id);
      if (pdfUrl) {
        setShowPdf(true);
        if (typeof section.page_idx === "number") setAnchorPage(section.page_idx);
        else setAnchorPage(undefined);
      }
    },
    [pdfUrl],
  );

  const ensureSectionContent = useCallback(async (section: Section, options?: { background?: boolean }) => {
    if (sectionContentRef.current[section.chunk_id]) return;
    const existing = sectionRequestsRef.current.get(section.chunk_id);
    if (existing) { await existing; return; }
    if (!options?.background) setLoadingChunk(section.chunk_id);
    const request = fetchApi<SectionContent>(`/api/sections/${section.chunk_id}`)
      .then((data) => setSectionContent((prev) => ({ ...prev, [section.chunk_id]: data })))
      .finally(() => {
        sectionRequestsRef.current.delete(section.chunk_id);
        if (!options?.background) setLoadingChunk((prev) => (prev === section.chunk_id ? null : prev));
      });
    sectionRequestsRef.current.set(section.chunk_id, request);
    await request;
  }, []);

  async function toggleSectionExpand(section: Section) {
    activateSection(section);
    if (expandedChunk === section.chunk_id) { setExpandedChunk(null); return; }
    setExpandedChunk(section.chunk_id);
    await ensureSectionContent(section);
  }

  return {
    doc, pdfUrl, downloadUrl, isAdmin, showPdf, setShowPdf, anchorPage, setAnchorPage,
    watermarkUrl, activeTab, setActiveTab, expandedChunk, activeChunk, sectionContent,
    loadingChunk, sectionSearch, setSectionSearch, sortedSections, activeSection,
    activeSectionLabel, visibleSections, sectionRequestsRef, sectionContentRef,
    refresh, handleDownload, activateSection, ensureSectionContent, toggleSectionExpand,
    handleSectionNavigate: activateSection, toggleSectionFavorite,
    clearActiveSectionSelection, getFavoriteId,
  };
}
