"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { fetchApi } from "@/lib/api";
import PdfPanel from "@/app/library/[doc_id]/PdfPanel";
import type { SourceSection } from "./types";

interface Props {
  source: SourceSection;
  onClose: () => void;
}

export function SourcePdfModal({ source, onClose }: Props) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchApi<{ preview_url: string }>(`/api/documents/${source.doc_id}/pdf-url`)
      .then((data) => {
        const token = localStorage.getItem("token") ?? "";
        setPdfUrl(`${data.preview_url}?token=${encodeURIComponent(token)}&t=${Date.now()}`);
      })
      .catch(() => setError(true));
  }, [source.doc_id]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-end bg-black/55 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex h-full w-[58%] min-w-[480px] max-w-[900px] flex-col shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {!pdfUrl ? (
          <div className="flex h-full flex-col items-center justify-center bg-gray-900 border-l border-gray-800">
            {error ? (
              <span className="text-sm text-gray-400">PDF 加载失败</span>
            ) : (
              <Loader2 size={24} className="animate-spin text-gray-500" />
            )}
          </div>
        ) : (
          <PdfPanel
            docId={source.doc_id}
            pdfUrl={pdfUrl}
            watermarkUrl=""
            canDownload={false}
            anchorPage={source.page_idx}
            anchorBBox={source.bbox ?? undefined}
            activeSectionNumber={source.number}
            activeSectionTitle={source.title}
            activeSectionLabel={source.number ? `§${source.number} ${source.title}` : source.title}
            onDownload={() => {}}
            onClose={onClose}
          />
        )}
      </div>
    </div>
  );
}
