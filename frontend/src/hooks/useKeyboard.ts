import { useEffect } from "react";
import { useRouter } from "next/navigation";

export function useGlobalKeyboard() {
    const router = useRouter();

    useEffect(() => {
        function handleKeyDown(e: KeyboardEvent) {
            // 忽略在输入框里的按键
            const tag = (e.target as HTMLElement).tagName;
            if (["INPUT", "TEXTAREA", "SELECT"].includes(tag)) return;

            // Cmd/Ctrl + K → 全局搜索
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                router.push("/search");
            }

            // Cmd/Ctrl + / → 智能问答
            if ((e.metaKey || e.ctrlKey) && e.key === "/") {
                e.preventDefault();
                router.push("/query");
            }

            // g + l → 文档库
            // g + s → 搜索
            // g + q → 问答
            // g + g → 图谱
        }

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [router]);
}