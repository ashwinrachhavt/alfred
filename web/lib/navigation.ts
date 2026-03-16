import {
  Bell,
  BookOpen,
  Calendar,
  LayoutGrid,
  MessageCircle,
  NotebookPen,
  NotepadText,
  Palette,
  Shapes,
  Sparkles,
  type LucideIcon,
} from "lucide-react";

export type NavGroup = "home" | "knowledge" | "research" | "practice" | "developer";

export type AppNavItem = {
  key: string;
  title: string;
  href: string;
  icon: LucideIcon;
  keywords: string[];
  group: NavGroup;
  /**
   * When true, surfaces in the top navigation on wide screens.
   * The sidebar always shows all primary items.
   */
  topNav?: boolean;
};

export const navGroupLabels: Record<NavGroup, string> = {
  home: "Home",
  knowledge: "Knowledge",
  research: "Research",
  practice: "Practice",
  developer: "Developer",
};

export const navGroupOrder: NavGroup[] = [
  "home",
  "knowledge",
  "research",
  "practice",
  "developer",
];

export const appNavItems: AppNavItem[] = [
  {
    key: "dashboard",
    title: "Dashboard",
    href: "/dashboard",
    icon: LayoutGrid,
    keywords: ["dashboard", "overview", "home"],
    group: "home",
  },
  {
    key: "library",
    title: "Library",
    href: "/library",
    icon: BookOpen,
    keywords: ["library", "documents", "notes", "files"],
    group: "knowledge",
  },
  {
    key: "notes",
    title: "Notes",
    href: "/notes",
    icon: NotebookPen,
    keywords: ["notes", "markdown", "editor", "tiptap", "second brain"],
    group: "knowledge",
  },
  {
    key: "notion",
    title: "Notion",
    href: "/notion",
    icon: NotepadText,
    keywords: ["notion", "integration", "sync", "import"],
    group: "knowledge",
  },
  {
    key: "rag",
    title: "RAG",
    href: "/rag",
    icon: MessageCircle,
    keywords: ["rag", "chat", "qa"],
    group: "knowledge",
  },
  {
    key: "company",
    title: "Research",
    href: "/company",
    icon: Sparkles,
    keywords: ["research", "deep research", "intel", "intelligence"],
    group: "research",
  },
  {
    key: "calendar",
    title: "Calendar & Email",
    href: "/calendar",
    icon: Calendar,
    keywords: ["calendar", "email", "gmail", "scan", "inbox"],
    group: "research",
  },
  {
    key: "system-design",
    title: "System Design",
    href: "/system-design",
    icon: Shapes,
    keywords: ["system design", "diagram", "architecture"],
    group: "practice",
  },
  {
    key: "design-system",
    title: "Design System",
    href: "/design-system",
    icon: Palette,
    keywords: ["design system", "ui", "components", "tokens"],
    group: "developer",
  },
];

export const appTopNavItems = appNavItems.filter((item) => item.topNav);
