"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Bell,
  BookA,
  BookOpen,
  Bot,
  Brain,
  Calendar,
  Inbox,
  LayoutDashboard,
  Network,
  NotebookPen,
  Orbit,
  Plug,
  Search,
  Settings,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { useShellStore } from "@/lib/stores/shell-store";
import { useTaskTracker } from "@/features/tasks/task-tracker-provider";

type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  shortcut?: string;
  action?: "toggle-ai-panel";
};

type NavSection = {
  title: string;
  items: NavItem[];
};

const navSections: NavSection[] = [
  {
    title: "Navigate",
    items: [
      { label: "Today", href: "/today", icon: Calendar },
      { label: "Alfred AI", href: "#ai", icon: Bot, shortcut: "0", action: "toggle-ai-panel" },
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
      { label: "Universe", href: "/universe", icon: Orbit },
      { label: "Dictionary", href: "/dictionary", icon: BookA },
    ],
  },
  {
    title: "System",
    items: [
      { label: "Connectors", href: "/connectors", icon: Plug },
      { label: "Settings", href: "/settings", icon: Settings },
    ],
  },
];

function SidebarNavItem({ item, isActive }: { item: NavItem; isActive: boolean }) {
  const { openAiPanel, aiPanelOpen, chatMode } = useShellStore();

  const aiActive = item.action === "toggle-ai-panel" && aiPanelOpen;
  const aiExpanded = item.action === "toggle-ai-panel" && chatMode === "expanded";

  const classes = cn(
    "group flex items-center gap-2.5 border-l-2 px-5 py-1.5 text-xs tracking-wide transition-colors",
    aiActive
      ? "border-primary bg-[var(--alfred-accent-subtle)] text-primary"
      : isActive
        ? "border-primary bg-[var(--alfred-accent-subtle)] text-primary"
        : "border-transparent text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
  );

  const inner = (
    <>
      <item.icon className="size-4 shrink-0 opacity-50 group-hover:opacity-100" />
      <span>{item.label}</span>
      {aiExpanded && (
        <span className="text-primary ml-1 text-[9px] tracking-wider uppercase opacity-70">
          expanded
        </span>
      )}
      {item.shortcut && (
        <kbd className="ml-auto text-[10px] text-[var(--alfred-text-tertiary)] opacity-0 transition-opacity group-hover:opacity-100">
          {item.shortcut}
        </kbd>
      )}
    </>
  );

  if (item.action === "toggle-ai-panel") {
    return (
      <button type="button" onClick={() => openAiPanel("expanded")} className={classes}>
        {inner}
      </button>
    );
  }

  return (
    <Link href={item.href} prefetch className={classes}>
      {inner}
    </Link>
  );
}

function TaskCenterButton() {
  const { activeCount, setTaskCenterOpen } = useTaskTracker();
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );

  // Only show badge after hydration to avoid server/client mismatch
  const showBadge = mounted && activeCount > 0;

  return (
    <button
      type="button"
      onClick={() => setTaskCenterOpen(true)}
      className="group text-muted-foreground hover:text-foreground flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-xs tracking-wide transition-colors hover:bg-[var(--alfred-accent-subtle)]"
    >
      <span className="relative">
        <Bell className="size-4" />
        {showBadge && (
          <span className="bg-primary text-primary-foreground absolute -top-1 -right-1 flex size-3.5 items-center justify-center rounded-full text-[8px] font-bold">
            {activeCount > 9 ? "9+" : activeCount}
          </span>
        )}
      </span>
      <span>Tasks</span>
      {showBadge && <span className="text-primary ml-auto text-[10px]">{activeCount} active</span>}
    </button>
  );
}

export function AppSidebar() {
  const pathname = usePathname();
  const openAiPanel = useShellStore((s) => s.openAiPanel);
  const aiPanelOpen = useShellStore((s) => s.aiPanelOpen);
  const chatMode = useShellStore((s) => s.chatMode);

  return (
    <aside className="hidden w-[220px] shrink-0 flex-col border-r bg-[var(--sidebar)] text-[var(--sidebar-foreground)] md:flex">
      {/* Logo */}
      <div className="flex h-12 items-center px-5">
        <Link href="/inbox" className="flex items-center gap-2">
          <span className="text-xl tracking-tight">Alfred</span>
          <span className="text-primary text-xl">.</span>
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

      {/* Task center + AI toggle at bottom */}
      <div className="space-y-1 border-t p-3">
        <TaskCenterButton />
        <button
          onClick={() => openAiPanel("expanded")}
          className={cn(
            "flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-xs tracking-wide transition-colors",
            aiPanelOpen
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground hover:bg-[var(--alfred-accent-subtle)]",
          )}
        >
          <Brain className="size-4" />
          <span>AI Assistant</span>
          {chatMode === "expanded" && (
            <span className="text-[9px] tracking-wider uppercase opacity-70">expanded</span>
          )}
          <kbd className="ml-auto text-[10px] opacity-60">J</kbd>
        </button>
      </div>
    </aside>
  );
}
