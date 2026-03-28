"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import Sidebar from "./Sidebar";

const NO_SIDEBAR_PATHS = ["/login", "/register"];

export default function ConditionalLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const router = useRouter();
    const showSidebar = !NO_SIDEBAR_PATHS.includes(pathname);

    useEffect(() => {
        if (!showSidebar) return;
        const token = localStorage.getItem("token");
        if (!token) {
            router.push("/login");
        }
    }, [pathname, showSidebar, router]);

    if (!showSidebar) {
        return <div className="min-h-screen bg-gray-950">{children}</div>;
    }

    return (
        <div className="flex h-screen bg-gray-950 overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-auto">{children}</main>
        </div>
    );
}