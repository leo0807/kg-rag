import type { Metadata } from "next";
import "./globals.css";
import ConditionalLayout from "./ConditionalLayout";
import { Toaster } from "sonner";

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
    <html lang="zh-CN" className="dark">
      <body>
        <ConditionalLayout>{children}</ConditionalLayout>
        <Toaster position="top-center" richColors closeButton />
      </body>
    </html>
  );
}
