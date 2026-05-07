"use client";

import { useSearchParams } from "next/navigation";
import type { MouseEvent } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useFavorites } from "@/app/favorites/useFavorites";
import { fetchApi } from "@/lib/api";
import { buildWatermarkUrl, getCurrentUser } from "./docDetailUtils";
import type {
  DocumentDetail,
  Section,
  SectionContent,
} from "./useDocDetailTypes";

export function useDocDetail(docId: string) {
  const searchParams = useSearchParams();
  const initialPage = searchParams.get("page");
  const initialSection = searchParams.get("section");

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
  const [showPdf, setShowPdf] = useState(
    initialPage !== null ||
      initialSection !== null ||
      searchParams.get("preview") === "true",
  );
  const [anchorPage, setAnchorPage] = useState<number | undefined>(() => {
    const parsed = parseInt(initialPage ?? "", 10);
    return Number.isFinite(parsed) ? parsed : undefined;
  });
  const [watermarkUrl, setWatermarkUrl] = useState("");
  const initialTab =
    (searchParams.get("tab") as "sections" | "drawings" | "reprocess" | null) ??
    "sections";
  const [activeTab, setActiveTab] = useState<
    "sections" | "drawings" | "reprocess"
  >(
    initialTab === "drawings" || initialTab === "reprocess"
      ? initialTab
      : "sections",
  );

  const sectionRequestsRef = useRef(new Map<string, Promise<void>>());
  const sectionContentRef = useRef<Record<string, SectionContent>>({});

  const { getFavoriteId, addFavorite, removeFavorite } = useFavorites();

  const clearActiveSectionSelection = useCallback(() => {
    setActiveChunk(null);
    setAnchorPage(undefined);
  }, []);

  useEffect(() => {
    sectionContentRef.current = sectionContent;
  }, [sectionContent]);

  useEffect(() => {
    const page = searchParams.get("page");
    if (page !== null) {
      const parsed = parseInt(page, 10);
      if (Number.isFinite(parsed)) {
        setAnchorPage(parsed);
        setShowPdf(true);
      }
    }
    if (searchParams.get("preview") === "true") setShowPdf(true);
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
    if (!docId) return;
    refresh();
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
        const preview = `${data.preview_url}?token=${encodeURIComponent(token)}&t=${Date.now()}`;
        setPdfUrl(preview);
      })
      .catch(() => {});
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

  useEffect(() => {
    if (!doc?.sections?.length || !initialSection) return;
    const found = doc.sections.find((s) => s.chunk_id === initialSection);
    if (!found) return;
    setActiveChunk((prev) => (prev === found.chunk_id ? prev : found.chunk_id));
    if (typeof found.page_idx === "number") setAnchorPage(found.page_idx);
    setShowPdf(true);
  }, [doc?.sections, initialSection]);

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
        if (typeof section.page_idx === "number")
          setAnchorPage(section.page_idx);
        else setAnchorPage(undefined);
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
      if (!options?.background) setLoadingChunk(section.chunk_id);
      const request = fetchApi<SectionContent>(
        `/api/sections/${section.chunk_id}`,
      )
        .then((data) =>
          setSectionContent((prev) => ({ ...prev, [section.chunk_id]: data })),
        )
        .finally(() => {
          sectionRequestsRef.current.delete(section.chunk_id);
          if (!options?.background)
            setLoadingChunk((prev) =>
              prev === section.chunk_id ? null : prev,
            );
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

  return {
    doc,
    pdfUrl,
    downloadUrl,
    isAdmin,
    showPdf,
    setShowPdf,
    anchorPage,
    setAnchorPage,
    watermarkUrl,
    activeTab,
    setActiveTab,
    expandedChunk,
    activeChunk,
    setActiveChunk,
    sectionContent,
    loadingChunk,
    sectionSearch,
    setSectionSearch,
    sectionRequestsRef,
    sectionContentRef,
    refresh,
    handleDownload,
    activateSection,
    ensureSectionContent,
    toggleSectionExpand,
    handleSectionNavigate: activateSection,
    toggleSectionFavorite,
    clearActiveSectionSelection,
    getFavoriteId,
  };
}
