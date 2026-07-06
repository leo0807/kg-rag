import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import ConditionalLayout from "./ConditionalLayout";
import { Toaster } from "sonner";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CPS 知识库 · 商飞大模型",
  description: "航空工艺规范智能知识图谱问答系统 v1.1.0",
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
    <html lang="zh-CN" data-scroll-behavior="smooth" className={`dark ${inter.variable} ${mono.variable}`}>
      <body>
        <ConditionalLayout>{children}</ConditionalLayout>
        <Toaster position="top-center" richColors closeButton />
        <script dangerouslySetInnerHTML={{ __html: `
          if ('serviceWorker' in navigator) {
            if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') {
              // Dev: unregister any lingering SW so stale chunks never block the page
              navigator.serviceWorker.getRegistrations().then(regs => {
                regs.forEach(r => r.unregister());
              });
            } else {
              window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js').then(() => {
                  let refreshing = false;
                  navigator.serviceWorker.addEventListener('controllerchange', () => {
                    if (!refreshing) { refreshing = true; window.location.reload(); }
                  });
                });
              });
            }
          }
        `}} />
      </body>
    </html>
  );
}
