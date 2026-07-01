"use client";

import { BookOpen, FileText, MessageSquare, Tag } from "lucide-react";

interface SuggestResult {
  documents:           { doc_id: string; title: string; relevance: number }[];
  sections:            { chunk_id: string; title: string; doc_id: string; relevance: number }[];
  entities:            { name: string; type: string; mention_count: number }[];
  suggested_questions: string[];
}

function Group({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-gray-800/60 last:border-0">
      <div className="flex items-center gap-1.5 px-3 pt-2 pb-1 text-[10px] font-semibold text-gray-500 uppercase tracking-widest">
        {icon}{label}
      </div>
      {children}
    </div>
  );
}
function Item({ children, onMouseDown }: { children: React.ReactNode; onMouseDown: () => void }) {
  return (
    <button type="button" onMouseDown={onMouseDown}
      className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-800/70 transition-colors text-left">
      {children}
    </button>
  );
}

interface Props {
  suggest:          SuggestResult;
  onSearchText:     (q: string) => void;
  onEntityClick:    (name: string) => void;
}

export function SuggestDropdown({ suggest, onSearchText, onEntityClick }: Props) {
  return (
    <div className="absolute top-full left-0 right-12 mt-1.5 bg-gray-900 border border-gray-700/60 rounded-xl shadow-2xl shadow-black/40 z-30 overflow-hidden">
      {suggest.documents.length > 0 && (
        <Group icon={<FileText size={11} className="text-indigo-400" />} label="文档">
          {suggest.documents.map(d => (
            <Item key={d.doc_id} onMouseDown={() => onSearchText(d.doc_id)}>
              <span className="font-mono text-indigo-400 text-xs shrink-0">{d.doc_id}</span>
              <span className="text-gray-400 text-xs truncate">{d.title}</span>
            </Item>
          ))}
        </Group>
      )}
      {suggest.sections.length > 0 && (
        <Group icon={<BookOpen size={11} className="text-amber-400" />} label="章节">
          {suggest.sections.map(s => (
            <Item key={s.chunk_id} onMouseDown={() => onSearchText(s.title)}>
              <span className="font-mono text-amber-400 text-xs shrink-0">{s.doc_id}</span>
              <span className="text-gray-300 text-xs truncate">{s.title}</span>
            </Item>
          ))}
        </Group>
      )}
      {suggest.entities.length > 0 && (
        <Group icon={<Tag size={11} className="text-emerald-400" />} label="相关实体">
          {suggest.entities.map(e => (
            <Item key={e.name} onMouseDown={() => onEntityClick(e.name)}>
              <span className="text-emerald-300 text-xs">{e.name}</span>
              <span className="text-gray-500 text-xs ml-auto">出现 {e.mention_count} 次</span>
            </Item>
          ))}
        </Group>
      )}
      {suggest.suggested_questions.length > 0 && (
        <Group icon={<MessageSquare size={11} className="text-violet-400" />} label="直接提问">
          {suggest.suggested_questions.map(q => (
            <Item key={q} onMouseDown={() => { window.location.href = `/query?q=${encodeURIComponent(q)}`; }}>
              <span className="text-violet-300 text-xs">{q}</span>
            </Item>
          ))}
        </Group>
      )}
    </div>
  );
}
