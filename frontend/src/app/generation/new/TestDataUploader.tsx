"use client";

import { fetchApi } from "@/lib/api";
import { Upload } from "lucide-react";
import { useRef, useState } from "react";

interface Props {
  taskId: string;
  onUploaded: (params: string[]) => void;
}

export function TestDataUploader({ taskId, onUploaded }: Props) {
  const [uploading, setUploading] = useState(false);
  const [done, setDone]           = useState(false);
  const [params, setParams]       = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const d = await fetchApi<{ rows: number; parameters: string[] }>(
        `/api/generation/tasks/${taskId}/upload-test-data`,
        { method: "POST", body: form }
      );
      setParams(d.parameters ?? []);
      setDone(true);
      onUploaded(d.parameters ?? []);
    } catch { /* silent */ }
    finally { setUploading(false); }
  };

  return (
    <div className="space-y-3">
      <div
        onDragOver={e => e.preventDefault()}
        onDrop={e => {
          e.preventDefault();
          const f = e.dataTransfer.files[0];
          if (f) handleFile(f);
        }}
        className="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center cursor-pointer hover:border-indigo-700 transition-colors"
        onClick={() => fileRef.current?.click()}
      >
        <Upload size={24} className="mx-auto mb-2 text-gray-600" />
        <p className="text-xs text-gray-500">
          {uploading ? "上传中…" : "拖入或点击选择 Excel / CSV 试验数据文件"}
        </p>
        <p className="text-[10px] text-gray-700 mt-1">
          格式：第一行表头，列：参数名 | 数值 | 单位 | 测试条件 | 备注
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          className="hidden"
          onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
        />
      </div>

      {done && params.length > 0 && (
        <div className="bg-green-900/20 border border-green-800 rounded-lg px-3 py-2">
          <p className="text-xs text-green-400 mb-1">上传成功，识别到 {params.length} 个参数：</p>
          <div className="flex flex-wrap gap-1">
            {params.slice(0, 12).map(p => (
              <span key={p} className="text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded">
                {p}
              </span>
            ))}
            {params.length > 12 && (
              <span className="text-[10px] text-gray-600">…+{params.length - 12}</span>
            )}
          </div>
        </div>
      )}

      <p className="text-[10px] text-gray-600">此步骤可选，跳过后可在任务详情页上传。</p>
    </div>
  );
}
