"use client";

import { Upload } from "lucide-react";

interface Props {
    dragging: boolean;
    running: boolean;
    onDragOver: () => void;
    onDragLeave: () => void;
    onDrop: (files: FileList) => void;
    onBrowse: () => void;
}

export function UploadDropzone({ dragging, running, onDragOver, onDragLeave, onDrop, onBrowse }: Props) {
    return (
        <div
            onDragOver={e => { e.preventDefault(); onDragOver(); }}
            onDragLeave={onDragLeave}
            onDrop={e => { e.preventDefault(); onDrop(e.dataTransfer.files); }}
            onClick={() => !running && onBrowse()}
            className={`border-2 border-dashed rounded-xl text-center transition-colors duration-200
                ${dragging ? "border-indigo-500 bg-indigo-500/10" : "border-gray-700 hover:border-gray-600 bg-gray-900/60"}
                ${running ? "opacity-40 cursor-not-allowed" : "cursor-pointer"} py-8`}
        >
            <Upload size={22} className={`mx-auto mb-2 ${dragging ? "text-indigo-400" : "text-gray-500"}`} />
            <div className="text-gray-200 text-sm font-medium">
                {dragging ? "松开以添加文件" : "拖拽文件到此处，或点击选择"}
            </div>
            <div className="flex items-center justify-center gap-3 mt-2">
                <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-500 font-mono">PDF</span>
                <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-500 font-mono">DOCX</span>
                <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-500 font-mono">DOC</span>
                <span className="text-xs text-gray-600">支持同时选择多个文件</span>
            </div>
        </div>
    );
}
