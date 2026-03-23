import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import Sidebar from "./Sidebar";

export const metadata: Metadata = {
  title: "CPS 知识库",
  description: "航空工艺规范智能问答系统",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="flex h-screen bg-gray-900 text-gray-100">
        {/* 侧边栏 */}
        <Sidebar />
        {/* 主内容区 */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </body>
    </html>
  );
}
