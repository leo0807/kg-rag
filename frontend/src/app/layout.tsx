import type { Metadata, Viewport } from "next";
import "./globals.css";
import ConditionalLayout from "./ConditionalLayout";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "CPS 知识库",
  description: "航空工艺规范智能问答系统",
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "CPS知识库" },
};

export const viewport: Viewport = {
  themeColor: "#030712",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
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
        <script dangerouslySetInnerHTML={{ __html: `
          if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js'));
          }
        `}} />
      </body>
    </html>
  );
}
