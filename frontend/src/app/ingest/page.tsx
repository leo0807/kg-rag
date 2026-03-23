"use client";

import { useState } from "react";

interface IngestResult {
    doc_id: string;
    sections: number;
    status: string;
}

export default function IngestPage() {
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const [result, setResult] = useState<string | null>(null);

    async function handleUpload() {
        if (!file) return;

        setLoading(true);
        setResult(null);

        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("http://localhost:8000/api/ingest", {
                method: "POST",
                body: formData,
            });

            const data = await res.json() as IngestResult;
            setResult(`写入成功${data.doc_id}，共${data.sections}个章节`);
        } catch (error) {
            setResult("上传失败，请检查后段服务");
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="p-8">
            <h1 className="text-2xl font-semibold text-white mb-6">导入文件</h1>
            <input type="file"
                accept=".pdf"
                onChange={e => {
                    const selected = e.target.files?.[0];
                    if (selected) setFile(selected);
                }}
                className="block text-sm text-gray-400"
            />
            {file && (
                <p className="mt-2 text-gray-300">
                    已选择：{file.name}（{(file.size / 1024).toFixed(1)} KB）
                </p>
            )}
            <button
                onClick={handleUpload}
                disabled={!file || loading}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm
                   disabled:opacity-50 disabled:cursor-not-allowed
                   hover:bg-indigo-500"
            >
                {loading ? "上传中..." : "上传并写入图谱"}
            </button>
            {
                result && (
                    <p className="mt-4 text-green-400">{result}</p>
                )
            }
        </div>
    )
}