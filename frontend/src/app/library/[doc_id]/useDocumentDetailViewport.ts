"use client";

import type { RefObject } from "react";
import { useEffect, useRef, useState } from "react";
import type { Section, SectionContent } from "./useDocDetailTypes";

type IdleDeadlineLike = { didTimeout: boolean; timeRemaining: () => number };
type IdleWindow = Window & {
  requestIdleCallback?: (
    cb: (dl: IdleDeadlineLike) => void,
    opts?: { timeout: number },
  ) => number;
  cancelIdleCallback?: (h: number) => void;
};

interface Props {
  doc: { sections: Section[] } | null;
  activeTab: "sections" | "drawings" | "reprocess";
  visibleSections: Section[];
  expandedChunk: string | null;
  ensureSectionContent: (
    section: Section,
    options?: { background?: boolean },
  ) => Promise<void>;
  sectionRequestsRef: RefObject<Map<string, Promise<void>>>;
  sectionContentRef: RefObject<Record<string, SectionContent>>;
  pdfUrl: string | null;
  setActiveTab: (tab: "sections" | "drawings" | "reprocess") => void;
}

export function useDocumentDetailViewport({
  doc,
  activeTab,
  visibleSections,
  expandedChunk,
  ensureSectionContent,
  sectionRequestsRef,
  sectionContentRef,
  pdfUrl,
  setActiveTab,
}: Props) {
  const [visibleSectionIds, setVisibleSectionIds] = useState<string[]>([]);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const sectionRowRefs = useRef(new Map<string, HTMLDivElement>());
  const highlightedRef = useRef(false);
  const visibleSectionIdsRef = useRef(new Set<string>());
  const idlePrefetchHandleRef = useRef<number | null>(null);
  const prefetchingChunkRef = useRef<string | null>(null);

  useEffect(() => {
    highlightedRef.current = false;
  }, []);

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
        const ordered = visibleSections
          .filter((s) => next.has(s.chunk_id))
          .map((s) => s.chunk_id);
        setVisibleSectionIds((prev) =>
          prev.length === ordered.length &&
          prev.every((v, i) => v === ordered[i])
            ? prev
            : ordered,
        );
      },
      { root, rootMargin: "140px 0px", threshold: 0.01 },
    );
    for (const section of visibleSections) {
      const node = sectionRowRefs.current.get(section.chunk_id);
      if (node) observer.observe(node);
    }
    return () => observer.disconnect();
  }, [activeTab, visibleSections, doc]);

  useEffect(() => {
    if (!doc || activeTab !== "sections" || !visibleSectionIds.length) return;
    if (prefetchingChunkRef.current) return;
    const queue = visibleSections.filter(
      (s) =>
        visibleSectionIds.includes(s.chunk_id) &&
        !sectionContentRef.current[s.chunk_id] &&
        !sectionRequestsRef.current.has(s.chunk_id) &&
        s.chunk_id !== expandedChunk,
    );
    const next = queue[0];
    if (!next) return;
    let cancelled = false;
    const idleWindow = window as IdleWindow;
    const runPrefetch = async (deadline: IdleDeadlineLike) => {
      if (cancelled) return;
      if (!deadline.didTimeout && deadline.timeRemaining() < 8) {
        schedulePrefetch();
        return;
      }
      prefetchingChunkRef.current = next.chunk_id;
      try {
        await ensureSectionContent(next, { background: true });
      } finally {
        prefetchingChunkRef.current = null;
        idlePrefetchHandleRef.current = null;
      }
    };
    const schedulePrefetch = () => {
      if (cancelled || idlePrefetchHandleRef.current !== null) return;
      if (idleWindow.requestIdleCallback) {
        idlePrefetchHandleRef.current = idleWindow.requestIdleCallback(
          (dl) => {
            idlePrefetchHandleRef.current = null;
            void runPrefetch(dl);
          },
          { timeout: 1200 },
        );
      } else {
        idlePrefetchHandleRef.current = window.setTimeout(() => {
          idlePrefetchHandleRef.current = null;
          void runPrefetch({ didTimeout: true, timeRemaining: () => 0 });
        }, 180);
      }
    };
    schedulePrefetch();
    return () => {
      cancelled = true;
      if (idlePrefetchHandleRef.current !== null) {
        if (idleWindow.cancelIdleCallback)
          idleWindow.cancelIdleCallback(idlePrefetchHandleRef.current);
        else window.clearTimeout(idlePrefetchHandleRef.current);
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
    sectionContentRef,
    sectionRequestsRef,
  ]);

  useEffect(() => {
    if (!doc || !visibleSections.length || highlightedRef.current) return;
    const params = new URLSearchParams(window.location.search);
    const targetId = params.get("section");
    if (!targetId) return;
    const found = visibleSections.find((s) => s.chunk_id === targetId);
    if (!found) return;
    if (params.get("preview") === "true" && !pdfUrl) return;
    highlightedRef.current = true;
    setActiveTab("sections");
    let attempt = 0;
    let timerId: ReturnType<typeof setTimeout>;
    const tryScroll = () => {
      const el = document.getElementById(`section-${targetId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.style.transition = "background-color 0.4s";
        el.style.backgroundColor = "rgba(234,179,8,0.18)";
        setTimeout(() => {
          el.style.backgroundColor = "";
        }, 3000);
      } else if (attempt < 20) {
        attempt++;
        timerId = setTimeout(tryScroll, 300);
      }
    };
    timerId = setTimeout(tryScroll, 300);
    return () => clearTimeout(timerId);
  }, [doc, visibleSections, pdfUrl, setActiveTab]);

  return { scrollContainerRef, sectionRowRefs };
}
