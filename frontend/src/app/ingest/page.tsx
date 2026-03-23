"use client";

import { useState } from "react";

export default function IngestPage() {
    const [file, setFile] = useState<File | null>(null);

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
        </div>
    )
}