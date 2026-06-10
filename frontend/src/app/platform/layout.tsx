import Link from "next/link";
import { ReactNode } from "react";

const NAV = [
  { href: "/platform/dashboard", label: "仪表盘" },
  { href: "/platform/tenants",   label: "租户管理" },
  { href: "/platform/usage",     label: "用量统计" },
];

export default function PlatformLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-950 text-white flex">
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-5 py-4 border-b border-gray-800">
          <div className="text-xs text-gray-500 uppercase tracking-widest mb-1">Platform</div>
          <div className="font-semibold text-white">超管控制台</div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href}
              className="block px-3 py-2 rounded text-sm text-gray-300 hover:bg-gray-800 hover:text-white">
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="p-3 border-t border-gray-800">
          <Link href="/" className="text-xs text-gray-500 hover:text-gray-300">← 返回应用</Link>
        </div>
      </aside>
      <main className="flex-1 p-8 overflow-auto">{children}</main>
    </div>
  );
}
