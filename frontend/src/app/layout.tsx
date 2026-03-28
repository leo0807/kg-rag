import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
import Sidebar from "./Sidebar";
import ConditionalLayout from "./ConditionalLayout";

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
      <body>
        <ConditionalLayout>{children}</ConditionalLayout>
      </body>
    </html>
  );
}
