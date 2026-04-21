"use client";

import { useEffect, useState } from "react";

export function useGraphTheme() {
    const [isDark, setIsDark] = useState(true);

    useEffect(() => {
        const sync = () => setIsDark(document.documentElement.classList.contains("dark"));
        sync();

        const observer = new MutationObserver(sync);
        observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
        return () => observer.disconnect();
    }, []);

    return isDark;
}

export function getGraphThemeColors(isDark: boolean) {
    return {
        backgroundColor: isDark ? 0x030712 : 0xf8fafc,
        labelFill: isDark ? "#ffffff" : "#0f172a",
        mutedLabelFill: isDark ? "#475569" : "#64748b",
        tooltipClassName: isDark
            ? "fixed hidden px-2 py-1 bg-gray-800 text-gray-100 text-xs rounded pointer-events-none border border-gray-700 max-w-xs"
            : "fixed hidden px-2 py-1 bg-white text-slate-900 text-xs rounded pointer-events-none border border-slate-200 shadow-lg max-w-xs",
        tooltipHintClass: isDark ? "text-gray-400" : "text-slate-500",
    };
}
