"use client";

import { ImageOff, Loader2, Pencil, Ruler } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { DrawingViewer } from "./DrawingViewer";

interface Annotation {
  type: string;
  raw: string;
  parameter: string;
  value: string;
  value_max: string;
  value_min: string;
  unit: string;
}

interface DrawingImage {
  image_id: string;
  caption: string;
  path: string;
  minio_path: string | null;
  url: string | null;
  description: string;
  is_drawing: boolean;
  part_numbers: string[];
  annotations: Annotation[];
  assembly_relations: string[];
  drawing_summary: string;
  annotations_count: number;
  section_chunk_id: string | null;
  section_number: string | null;
  section_title: string | null;
}

interface ImagesResponse {
  images?: DrawingImage[];
  total?: number;
  drawing_total?: number;
  has_more?: boolean;
}

interface Props {
  docId: string;
  targetImageId?: string;
}

const PAGE_SIZE = 36;

export function DrawingsTab({ docId, targetImageId }: Props) {
  const [images, setImages] = useState<DrawingImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [selected, setSelected] = useState<DrawingImage | null>(null);
  const [reanalyzing, setReanalyzing] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "drawing">("all");
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [drawingTotal, setDrawingTotal] = useState(0);
  const [loadedPages, setLoadedPages] = useState(1);
  const requestSeqRef = useRef(0);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const fetchImages = useCallback(
    async (
      page: number,
      options?: {
        replace?: boolean;
        pageSize?: number;
        nextFilter?: "all" | "drawing";
      },
    ) => {
      const token = localStorage.getItem("token") ?? "";
      const replace = options?.replace ?? false;
      const pageSize = options?.pageSize ?? PAGE_SIZE;
      const nextFilter = options?.nextFilter ?? filter;
      const params = new URLSearchParams({
        page: String(page),
        per_page: String(pageSize),
      });

      if (nextFilter === "drawing") {
        params.set("drawing_only", "true");
      }

      const requestSeq = ++requestSeqRef.current;
      if (replace) {
        setLoading(true);
      } else {
        setLoadingMore(true);
      }

      try {
        const response = await fetch(
          `/api/documents/${docId}/images?${params.toString()}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        );
        const data = (await response.json()) as ImagesResponse;
        if (requestSeq !== requestSeqRef.current) return;

        const nextImages = (data.images ?? []).filter((img) => !!img.image_id);

        setImages((prev) => {
          const merged = replace
            ? nextImages
            : [
                ...prev,
                ...nextImages.filter(
                  (img) =>
                    !prev.some(
                      (existing) => existing.image_id === img.image_id,
                    ),
                ),
              ];

          setSelected((current) =>
            current
              ? (merged.find((img) => img.image_id === current.image_id) ??
                null)
              : null,
          );
          return merged;
        });
        setTotal(data.total ?? 0);
        setDrawingTotal(data.drawing_total ?? 0);
        setHasMore(Boolean(data.has_more));
      } catch {
        if (replace) {
          setImages([]);
          setTotal(0);
          setDrawingTotal(0);
          setHasMore(false);
          setSelected(null);
        }
      } finally {
        if (requestSeq === requestSeqRef.current) {
          setLoading(false);
          setLoadingMore(false);
        }
      }
    },
    [docId, filter],
  );

  useEffect(() => {
    if (!docId) {
      setLoading(false);
      return;
    }
    setImages([]);
    setSelected(null);
    setHasMore(false);
    setLoadedPages(1);
    void fetchImages(1, { replace: true, nextFilter: filter });
  }, [docId, filter, fetchImages]);

  useEffect(() => {
    if (!hasMore || loading || loadingMore) return;
    const node = sentinelRef.current;
    if (!node) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) return;
        const nextPage = loadedPages + 1;
        setLoadedPages(nextPage);
        void fetchImages(nextPage, { nextFilter: filter });
      },
      { rootMargin: "320px 0px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [fetchImages, filter, hasMore, loadedPages, loading, loadingMore]);

  // Scroll to and highlight a specific image when navigated from graph (?image_id=xxx)
  useEffect(() => {
    if (!targetImageId || loading || images.length === 0) return;
    const found = images.find(img => img.image_id === targetImageId);
    if (!found) return;
    let attempt = 0;
    let timerId: ReturnType<typeof setTimeout>;
    const tryScroll = () => {
      const el = document.getElementById(`image-${targetImageId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.style.transition = "outline 0.1s";
        el.style.outline = "3px solid #6366f1";
        setTimeout(() => { el.style.outline = ""; }, 3000);
      } else if (attempt < 5) {
        attempt++;
        timerId = setTimeout(tryScroll, 150);
      }
    };
    timerId = setTimeout(tryScroll, 300);
    return () => clearTimeout(timerId);
  }, [targetImageId, images, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  async function refreshLoadedImages() {
    await fetchImages(1, {
      replace: true,
      pageSize: PAGE_SIZE * loadedPages,
      nextFilter: filter,
    });
  }

  async function handleReanalyze(imageId: string) {
    setReanalyzing(imageId);
    const token = localStorage.getItem("token") ?? "";
    try {
      await fetch(`/api/documents/${docId}/images/${imageId}/analyze-drawing`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      window.setTimeout(() => {
        void refreshLoadedImages().finally(() => setReanalyzing(null));
      }, 8000);
    } catch {
      setReanalyzing(null);
    }
  }

  const visibleTotal = filter === "drawing" ? drawingTotal : total;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-gray-500 text-sm gap-2">
        <Loader2 size={16} className="animate-spin" />
        加载图片中...
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-600 gap-3">
        <ImageOff size={32} strokeWidth={1.5} />
        <div className="text-sm">本文档暂无提取到的图片</div>
        <div className="text-xs text-gray-700">
          重新入库文档后图片将自动提取并分析
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="flex items-center gap-2 mb-4">
        {(["all", "drawing"] as const).map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setFilter(item)}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
              filter === item
                ? "bg-indigo-600 text-white"
                : "text-gray-400 hover:text-white bg-gray-800 border border-gray-700"
            }`}
          >
            {item === "all"
              ? `全部图片 (${total})`
              : `工程图纸 (${drawingTotal})`}
          </button>
        ))}
        <span className="ml-auto text-xs text-gray-600">
          已加载 {images.length} / {visibleTotal}
        </span>
      </div>

      {images.length === 0 ? (
        <div className="text-center py-12 text-gray-600 text-sm">
          暂无工程图纸
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {images.map((img) => {
              const src = img.url ?? null;
              return (
                <button
                  key={img.image_id}
                  id={`image-${img.image_id}`}
                  type="button"
                  onClick={() => setSelected(img)}
                  className="group relative bg-gray-900 border border-gray-800 rounded-xl
                                               overflow-hidden hover:border-indigo-500 transition-colors text-left"
                >
                  <div className="aspect-[4/3] overflow-hidden bg-gray-800 flex items-center justify-center">
                    {src ? (
                      <img
                        src={src}
                        alt={img.caption || "图片"}
                        loading="lazy"
                        decoding="async"
                        className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-200"
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).style.display =
                            "none";
                          (
                            e.currentTarget.nextSibling as HTMLElement | null
                          )?.removeAttribute("hidden");
                        }}
                      />
                    ) : null}
                    <span
                      hidden={!!src}
                      className="text-xs text-gray-600 px-3 text-center"
                    >
                      图片暂不可用
                    </span>
                  </div>
                  <div className="px-3 py-2">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      {img.is_drawing && (
                        <Ruler size={10} className="text-indigo-400 shrink-0" />
                      )}
                      <span className="text-xs text-gray-300 truncate">
                        {img.caption || img.drawing_summary || "图片"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-gray-600 font-mono truncate">
                        {img.section_number
                          ? `§${img.section_number}`
                          : "未归属章节"}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0">
                        {img.annotations_count > 0 && (
                          <span className="text-xs text-indigo-400">
                            {img.annotations_count} 条标注
                          </span>
                        )}
                        {reanalyzing === img.image_id && (
                          <Loader2
                            size={10}
                            className="animate-spin text-amber-400"
                          />
                        )}
                      </div>
                    </div>
                  </div>
                  {!img.annotations_count && (
                    <div
                      className="absolute top-2 right-2 p-1 bg-gray-900/80 rounded"
                      title="未提取到尺寸标注"
                    >
                      <Pencil size={10} className="text-gray-500" />
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {(hasMore || loadingMore) && (
            <div
              ref={sentinelRef}
              className="flex items-center justify-center py-5 text-xs text-gray-600 gap-2"
            >
              {loadingMore ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  加载更多图片中...
                </>
              ) : (
                <span>继续向下滚动以加载更多图片</span>
              )}
            </div>
          )}
        </>
      )}

      {selected && (
        <DrawingViewer
          image={selected}
          onClose={() => setSelected(null)}
          onReanalyze={handleReanalyze}
          reanalyzing={reanalyzing === selected.image_id}
        />
      )}
    </>
  );
}
