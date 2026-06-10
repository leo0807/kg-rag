"use client";

import { ArrowLeft, BookOpen, ChevronRight, FileText, Package } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";

interface WikiCard {
  doc_id: string;
  title: string;
  spec_type: string;
  summary: string;
  scope: string;
  key_terms: { term: string; definition: string }[];
  related_specs: { doc_id: string; title: string }[];
  main_processes: { title: string; summary: string }[];
  involved_materials: string[];
}

export default function WikiCardPage() {
  const { doc_id } = useParams<{ doc_id: string }>();
  const [card, setCard] = useState<WikiCard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!doc_id) return;
    fetchApi<WikiCard>(`/api/wiki/${doc_id}`)
      .then(setCard)
      .catch(() => setError("规范不存在或加载失败"))
      .finally(() => setLoading(false));
  }, [doc_id]);

  if (loading) {
    return (
      <div className="flex-1 overflow-auto bg-gray-950 p-6 flex items-center justify-center">
        <p className="text-xs text-gray-600">加载中…</p>
      </div>
    );
  }

  if (error || !card) {
    return (
      <div className="flex-1 overflow-auto bg-gray-950 p-6">
        <Link href="/wiki" className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 mb-6">
          <ArrowLeft size={12} /> 返回列表
        </Link>
        <p className="text-sm text-red-400 text-center py-12">{error || "未知错误"}</p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-auto bg-gray-950 p-6">
      <div className="max-w-3xl mx-auto">
        <Link href="/wiki" className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 mb-6">
          <ArrowLeft size={12} /> 返回列表
        </Link>

        {/* Title card */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-5">
          <div className="flex items-start gap-3">
            <BookOpen size={20} className="text-indigo-400 shrink-0 mt-0.5" />
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-mono font-semibold text-indigo-400">{card.doc_id}</span>
                {card.spec_type && (
                  <span className="text-[10px] px-2 py-0.5 bg-indigo-900/40 text-indigo-300 rounded-full">
                    {card.spec_type}
                  </span>
                )}
              </div>
              <h1 className="text-lg font-semibold text-gray-100">{card.title}</h1>
              {card.summary && (
                <p className="text-sm text-gray-400 mt-2 leading-relaxed">{card.summary}</p>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Scope */}
          {card.scope && (
            <Section title="适用范围" icon={<FileText size={13} />} className="md:col-span-2">
              <p className="text-sm text-gray-400 leading-relaxed whitespace-pre-line">{card.scope}</p>
            </Section>
          )}

          {/* Key Terms */}
          {card.key_terms.length > 0 && (
            <Section title="关键术语">
              <ul className="space-y-2">
                {card.key_terms.map((t, i) => (
                  <li key={i}>
                    <span className="text-xs font-medium text-indigo-300">{t.term}</span>
                    <p className="text-xs text-gray-500 mt-0.5">{t.definition}</p>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* Related Specs */}
          {card.related_specs.length > 0 && (
            <Section title="引用规范">
              <ul className="space-y-1.5">
                {card.related_specs.map((s) => (
                  <li key={s.doc_id}>
                    <Link href={`/wiki/${s.doc_id}`}
                      className="flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
                      <ChevronRight size={10} />
                      <span className="font-mono">{s.doc_id}</span>
                      {s.title && <span className="text-gray-500 truncate">— {s.title}</span>}
                    </Link>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {/* Main Processes */}
          {card.main_processes.length > 0 && (
            <Section title="主要工艺" className="md:col-span-2">
              <div className="space-y-3">
                {card.main_processes.map((p, i) => (
                  <div key={i} className="bg-gray-800/50 rounded-lg p-3">
                    <p className="text-xs font-medium text-gray-200 mb-1">{p.title}</p>
                    <p className="text-xs text-gray-500 leading-relaxed">{p.summary}</p>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Materials */}
          {card.involved_materials.length > 0 && (
            <Section title="涉及材料" icon={<Package size={13} />}>
              <div className="flex flex-wrap gap-1.5">
                {card.involved_materials.map((m, i) => (
                  <span key={i} className="text-[11px] px-2 py-0.5 bg-gray-800 text-gray-300 rounded-full">
                    {m}
                  </span>
                ))}
              </div>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({
  title, icon, children, className = "",
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-xl p-4 ${className}`}>
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5 mb-3">
        {icon}{title}
      </h2>
      {children}
    </div>
  );
}
