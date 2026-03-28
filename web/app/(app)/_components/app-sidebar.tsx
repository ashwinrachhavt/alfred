"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  BookOpen,
  Bot,
  Brain,
  Inbox,
  LayoutDashboard,
  Network,
  NotebookPen,
  Plug,
  Search,
  Settings,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { useShellStore } from "@/lib/stores/shell-store";

type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  shortcut?: string;
};

type NavSection = {
  title: string;
  items: NavItem[];
};

const navSections: NavSection[] = [
  {
    title: "Navigate",
    items: [
      { label: "Alfred Agent", href: "/agent", icon: Bot, shortcut: "0" },
      { label: "Inbox", href: "/inbox", icon: Inbox, shortcut: "1" },
      { label: "Canvas", href: "/canvas", icon: Network, shortcut: "2" },
      { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, shortcut: "4" },
      { label: "Notes", href: "/notes", icon: NotebookPen },
    ],
  },
  {
    title: "Discover",
    items: [
      { label: "Research", href: "/research", icon: Search },
      { label: "Knowledge", href: "/knowledge", icon: BookOpen },
    ],
  },
  {
    title: "System",
    items: [
      { label: "Connectors", href: "/notion", icon: Plug },
      { label: "Settings", href: "/settings", icon: Settings },
    ],
  },
];

function SidebarNavItem({ item, isActive }: { item: NavItem; isActive: boolean }) {
  return (
    <Link
      href={item.href}
      className={cn(
        "group flex items-center gap-2.5 border-l-2 px-5 py-1.5 font-mono text-xs tracking-wide transition-colors",
        isActive
          ? "border-primary bg-[var(--alfred-accent-subtle)] text-primary"
          : "border-transparent text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
      )}
    >
      <item.icon className="size-4 shrink-0 opacity-50 group-hover:opacity-100" />
      <span>{item.label}</span>
      {item.shortcut && (
        <kbd className="ml-auto text-[10px] text-[var(--alfred-text-tertiary)] opacity-0 group-hover:opacity-100 transition-opacity">
          {item.shortcut}
        </kbd>
      )}
    </Link>
  );
}

export function AppSidebar() {
  const pathname = usePathname();
  const toggleAiPanel = useShellStore((s) => s.toggleAiPanel);
  const aiPanelOpen = useShellStore((s) => s.aiPanelOpen);

  return (
    <aside className="hidden md:flex w-[220px] shrink-0 flex-col border-r bg-[var(--sidebar)] text-[var(--sidebar-foreground)]">
      {/* Logo */}
      <div className="flex h-12 items-center px-5">
        <Link href="/inbox" className="flex items-center gap-2">
          <span className="font-serif text-xl tracking-tight">Alfred</span>
          <span className="text-primary text-xl font-serif">.</span>
        </Link>
      </div>

      {/* Navigation sections */}
      <nav className="flex-1 overflow-y-auto py-2" aria-label="Primary navigation">
        {navSections.map((section) => (
          <div key={section.title} className="mb-2">
            <div className="label-mono px-5 py-2 text-[var(--alfred-text-tertiary)]">
              {section.title}
            </div>
            {section.items.map((item) => {
              const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return <SidebarNavItem key={item.href} item={item} isActive={isActive} />;
            })}
          </div>
        ))}
      </nav>

      {/* AI toggle at bottom */}
      <div className="border-t p-3">
        <button
          onClick={toggleAiPanel}
          className={cn(
            "flex w-full items-center gap-2.5 rounded-md px-3 py-2 font-mono text-xs tracking-wide transition-colors",
            aiPanelOpen
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
          )}
        >
          <Brain className="size-4" />
          <span>AI Assistant</span>
          <kbd className="ml-auto text-[10px] opacity-60">J</kbd>
        </button>
      </div>
    </aside>
  );
}
