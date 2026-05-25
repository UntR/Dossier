import type { Metadata } from "next";
import type React from "react";
import Link from "next/link";
import { Suspense } from "react";
import { GlobalSearch } from "@/components/global-search";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dossier",
  description: "本地关系记忆库"
};

const navItems = [
  { href: "/chat", label: "对话" },
  { href: "/people", label: "人物" },
  { href: "/entities", label: "实体" },
  { href: "/timeline", label: "时间树" },
  { href: "/inbox", label: "审核" },
  { href: "/import", label: "导入" },
  { href: "/self", label: "我的画像" },
  { href: "/settings", label: "设置" }
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="min-h-screen bg-slate-50 text-slate-950">
          <header className="border-b border-slate-200 bg-white">
            <div className="mx-auto flex max-w-7xl items-center gap-6 px-6 py-4">
              <Link href="/chat" className="text-lg font-semibold">
                Dossier
              </Link>
              <nav className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
                {navItems.map((item) => (
                  <Link key={item.href} href={item.href} className="rounded px-2 py-1 hover:bg-slate-100">
                    {item.label}
                  </Link>
                ))}
              </nav>
              <Suspense fallback={<Link href="/search" className="ml-auto rounded border border-slate-200 px-3 py-1.5 text-sm">搜索</Link>}>
                <GlobalSearch />
              </Suspense>
            </div>
          </header>
          <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
