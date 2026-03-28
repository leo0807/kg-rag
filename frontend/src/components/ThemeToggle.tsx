"use client";

import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";

export default function ThemeToggle() {
    const [isDark, setIsDark] = useState(true);

    useEffect(() => {
        // 读取保存的主题
        const saved = localStorage.getItem("theme");
        const dark = saved ? saved === "dark" : true;
        setIsDark(dark);
        document.documentElement.classList.toggle("dark", dark);
    }, []);

    function toggle() {
        const next = !isDark;
        setIsDark(next);
        document.documentElement.classList.toggle("dark", next);
        localStorage.setItem("theme", next ? "dark" : "light");
    }

    return (
        <button
            onClick={toggle}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white
                 hover:bg-gray-800 transition-colors"
            title={isDark ? "切换浅色" : "切换深色"}
        >
            {isDark ? <Sun size={16} /> : <Moon size={16} />}
        </button>
    );
}