"use client";

import { useEffect } from "react";
import { X } from "lucide-react";

const SHORTCUTS = [
    { keys: ["Cmd/Ctrl", "K"], desc: "全局搜索" },
    { keys: ["Cmd/Ctrl", "/"], desc: "智能问答" },
    { keys: ["?"], desc: "显示此帮助" },
];

function Key({ label }: { label: string }) {
    return (
        <kbd className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-semibold bg-gray-700 text-gray-200 border border-gray-600">
            {label}
        </kbd>
    );
}

export default function ShortcutsModal({
    open,
    onClose,
}: {
    open: boolean;
    onClose: () => void;
}) {
    useEffect(() => {
        if (!open) return;
        function onKey(e: KeyboardEvent) {
            if (e.key === "Escape") onClose();
        }
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
            onClick={onClose}
        >
            <div
                className="relative w-full max-w-sm mx-4 rounded-xl bg-gray-900 border border-gray-700 shadow-2xl p-6"
                onClick={e => e.stopPropagation()}
            >
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 p-1 rounded text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
                    aria-label="关闭"
                >
                    <X size={16} />
                </button>

                <h2 className="text-sm font-semibold text-white mb-4">键盘快捷键</h2>

                <ul className="space-y-3">
                    {SHORTCUTS.map(({ keys, desc }) => (
                        <li key={desc} className="flex items-center justify-between gap-4">
                            <span className="text-sm text-gray-300">{desc}</span>
                            <span className="flex items-center gap-1 shrink-0">
                                {keys.map((k, i) => (
                                    <span key={k} className="flex items-center gap-1">
                                        {i > 0 && <span className="text-gray-500 text-xs">+</span>}
                                        <Key label={k} />
                                    </span>
                                ))}
                            </span>
                        </li>
                    ))}
                </ul>

                <p className="mt-5 text-xs text-gray-600 text-center">按 ESC 或点击空白处关闭</p>
            </div>
        </div>
    );
}
