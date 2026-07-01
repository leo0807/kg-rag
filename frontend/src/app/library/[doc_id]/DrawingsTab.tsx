"use client";

import { ImageOff, Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { fetchApi } from "@/lib/api";
import { DrawingViewer } from "./DrawingViewer";
import { DrawingCard, type DrawingImage } from "./DrawingCard";

interface ImagesResponse {
  images?: DrawingImage[];
  total?: number;
  drawing_total?: number;
  has_more?: boolean;
}

interface Props { docId: string; targetImageId?: string }

const PAGE_SIZE = 36;

export function DrawingsTab({ docId, targetImageId }: Props) {
  const [images,       setImages]       = useState<DrawingImage[]>([]);
  const [loading,      setLoading]      = useState(true);
  const [loadingMore,  setLoadingMore]  = useState(false);
  const [selected,     setSelected]     = useState<DrawingImage | null>(null);
  const [reanalyzing,  setReanalyzing]  = useState<string | null>(null);
  const [filter,       setFilter]       = useState<"all" | "drawing">("all");
  const [hasMore,      setHasMore]      = useState(false);
  const [total,        setTotal]        = useState(0);
  const [drawingTotal, setDrawingTotal] = useState(0);
  const [loadedPages,  setLoadedPages]  = useState(1);
  const requestSeqRef = useRef(0);
  const sentinelRef   = useRef<HTMLDivElement | null>(null);

  const fetchImages = useCallback(async (
    page: number,
    options?: { replace?: boolean; pageSize?: number; nextFilter?: "all" | "drawing" },
  ) => {
    const replace    = options?.replace    ?? false;
    const pageSize   = options?.pageSize   ?? PAGE_SIZE;
    const nextFilter = options?.nextFilter ?? filter;
    const params = new URLSearchParams({ page: String(page), per_page: String(pageSize) });
    if (nextFilter === "drawing") params.set("drawing_only", "true");

    const seq = ++requestSeqRef.current;
    replace ? setLoading(true) : setLoadingMore(true);

    try {
      const data = await fetchApi<ImagesResponse>(`/api/documents/${docId}/images?${params}`);
      if (seq !== requestSeqRef.current) return;
      const next = (data.images ?? []).filter(img => !!img.image_id);
      setImages(prev => {
        const merged = replace ? next : [...prev, ...next.filter(n => !prev.some(p => p.image_id === n.image_id))];
        setSelected(cur => cur ? (merged.find(i => i.image_id === cur.image_id) ?? null) : null);
        return merged;
      });
      setTotal(data.total ?? 0);
      setDrawingTotal(data.drawing_total ?? 0);
      setHasMore(Boolean(data.has_more));
    } catch {
      if (replace) { setImages([]); setTotal(0); setDrawingTotal(0); setHasMore(false); setSelected(null); }
    } finally {
      if (seq === requestSeqRef.current) { setLoading(false); setLoadingMore(false); }
    }
  }, [docId, filter]);

  useEffect(() => {
    if (!docId) { setLoading(false); return; }
    setImages([]); setSelected(null); setHasMore(false); setLoadedPages(1);
    void fetchImages(1, { replace: true, nextFilter: filter });
  }, [docId, filter, fetchImages]);

  useEffect(() => {
    if (!hasMore || loading || loadingMore) return;
    const node = sentinelRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(entries => {
      if (!entries.some(e => e.isIntersecting)) return;
      const nextPage = loadedPages + 1;
      setLoadedPages(nextPage);
      void fetchImages(nextPage, { nextFilter: filter });
    }, { rootMargin: "320px 0px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [fetchImages, filter, hasMore, loadedPages, loading, loadingMore]);

  useEffect(() => {
    if (!targetImageId || loading || images.length === 0) return;
    if (!images.find(img => img.image_id === targetImageId)) return;
    let attempt = 0, timerId: ReturnType<typeof setTimeout>;
    const tryScroll = () => {
      const el = document.getElementById(`image-${targetImageId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.style.transition = "outline 0.1s";
        el.style.outline = "3px solid #6366f1";
        setTimeout(() => { el.style.outline = ""; }, 3000);
      } else if (attempt < 5) { attempt++; timerId = setTimeout(tryScroll, 150); }
    };
    timerId = setTimeout(tryScroll, 300);
    return () => clearTimeout(timerId);
  }, [targetImageId, images, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleReanalyze(imageId: string) {
    setReanalyzing(imageId);
    try {
      await fetchApi(`/api/documents/${docId}/images/${imageId}/analyze-drawing`, { method: "POST" });
      window.setTimeout(() => {
        void fetchImages(1, { replace: true, pageSize: PAGE_SIZE * loadedPages, nextFilter: filter })
          .finally(() => setReanalyzing(null));
      }, 8000);
    } catch { setReanalyzing(null); }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-16 text-gray-500 text-sm gap-2">
      <Loader2 size={16} className="animate-spin" /> 加载图片中...
    </div>
  );

  if (total === 0) return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-600 gap-3">
      <ImageOff size={32} strokeWidth={1.5} />
      <div className="text-sm">本文档暂无提取到的图片</div>
      <div className="text-xs text-gray-700">重新入库文档后图片将自动提取并分析</div>
    </div>
  );

  const visibleTotal = filter === "drawing" ? drawingTotal : total;

  return (
    <>
      <div className="flex items-center gap-2 mb-4">
        {(["all", "drawing"] as const).map(item => (
          <button key={item} type="button" onClick={() => setFilter(item)}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
              filter === item ? "bg-indigo-600 text-white" : "text-gray-400 hover:text-white bg-gray-800 border border-gray-700"
            }`}>
            {item === "all" ? `全部图片 (${total})` : `工程图纸 (${drawingTotal})`}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-600">已加载 {images.length} / {visibleTotal}</span>
      </div>

      {images.length === 0 ? (
        <div className="text-center py-12 text-gray-600 text-sm">暂无工程图纸</div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {images.map(img => (
              <DrawingCard key={img.image_id} img={img}
                reanalyzing={reanalyzing === img.image_id}
                onSelect={setSelected} />
            ))}
          </div>
          {(hasMore || loadingMore) && (
            <div ref={sentinelRef} className="flex items-center justify-center py-5 text-xs text-gray-600 gap-2">
              {loadingMore ? (<><Loader2 size={14} className="animate-spin" />加载更多图片中...</>) : <span>继续向下滚动以加载更多图片</span>}
            </div>
          )}
        </>
      )}

      {selected && (
        <DrawingViewer image={selected} onClose={() => setSelected(null)}
          onReanalyze={handleReanalyze} reanalyzing={reanalyzing === selected.image_id} />
      )}
    </>
  );
}
