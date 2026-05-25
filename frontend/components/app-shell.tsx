"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, GitBranch, Inbox, MessageSquare, Settings, UserRound, Users } from "lucide-react";

import { GlobalSearch } from "@/components/global-search";

const navItems = [
  { href: "/chat", label: "对话", icon: MessageSquare },
  { href: "/people", label: "人物", icon: Users },
  { href: "/inbox", label: "审核", icon: Inbox },
  { href: "/timeline", label: "时间树", icon: GitBranch },
  { href: "/self", label: "我的画像", icon: UserRound },
  { href: "/settings", label: "设置", icon: Settings }
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="grid min-h-screen bg-[color:var(--dossier-bg)] text-[color:var(--dossier-ink)] lg:grid-cols-[232px_minmax(0,1fr)]">
      <aside className="border-b border-[color:var(--dossier-line)] bg-[color:var(--dossier-rail)] p-4 lg:border-b-0 lg:border-r">
        <Link href="/chat" className="mb-4 flex items-center gap-2 px-2 text-xl font-bold">
          <Brain size={22} aria-hidden="true" />
          <span>Dossier</span>
        </Link>
        <nav className="grid gap-1 sm:grid-cols-3 lg:grid-cols-1" aria-label="主导航">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-10 items-center gap-3 rounded-[8px] px-3 text-sm font-semibold transition ${
                  active
                    ? "bg-[color:var(--dossier-green)] text-[color:var(--dossier-panel)]"
                    : "text-[color:var(--dossier-ink)] hover:bg-[color:var(--dossier-panel-muted)]"
                }`}
              >
                <Icon size={17} aria-hidden="true" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="grid min-w-0 grid-rows-[auto_1fr]">
        <header className="sticky top-0 z-20 border-b border-[color:var(--dossier-line)] bg-[rgba(255,253,247,0.9)] px-4 py-3 backdrop-blur md:px-6">
          <div className="flex items-center gap-3">
            <GlobalSearch />
            <span className="dossier-chip hidden md:inline-flex">本地数据</span>
          </div>
        </header>
        <main className="min-w-0 px-4 py-5 md:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
