import { useState } from "react";

interface Props {
  sections: Record<string, string>;
}

const SECTION_TITLES: Record<string, string> = {
  "1": "范围", "2": "引用文件", "3": "术语和定义",
  "4": "材料", "6": "技术要求", "7": "工艺规程",
  "8": "检验与试验", "9": "标识与记录",
};
const ORDER = ["1", "2", "3", "4", "6", "7", "8", "9"];

export function SectionPreview({ sections }: Props) {
  const [open, setOpen] = useState<string | null>(null);

  const doneSections = ORDER.filter(n => sections[n]);
  if (doneSections.length === 0) return null;

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
        已生成章节预览
      </h3>
      {doneSections.map(num => (
        <div key={num}
          className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <button
            type="button"
            onClick={() => setOpen(o => o === num ? null : num)}
            className="w-full flex items-center justify-between px-4 py-2.5 text-xs text-gray-300 hover:bg-gray-800/50 transition-colors"
          >
            <span className="font-medium">§{num} {SECTION_TITLES[num] ?? ""}</span>
            <span className="text-gray-600">
              {open === num ? "▲" : "▼"} {sections[num].split(/\s+/).length} 词
            </span>
          </button>
          {open === num && (
            <div className="px-4 pb-4 pt-1 text-xs text-gray-400 whitespace-pre-wrap leading-relaxed max-h-64 overflow-auto border-t border-gray-800">
              {sections[num]}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
