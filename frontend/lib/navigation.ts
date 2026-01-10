import {
  Brain,
  BookOpen,
  Calendar,
  Command,
  Feather,
  FileText,
  Globe,
  Home,
  LayoutGrid,
  MessageCircle,
  MessageSquareText,
  Network,
  NotepadText,
  Palette,
  PenTool,
  Shield,
  Shapes,
  Sparkles,
  Wrench,
  type LucideIcon,
} from "lucide-react";

export type AppNavItem = {
  key: string;
  title: string;
  href: string;
  icon: LucideIcon;
  keywords: string[];
  /**
   * When true, surfaces in the top navigation on wide screens.
   * The sidebar always shows all primary items.
   */
  topNav?: boolean;
};

export const appNavItems: AppNavItem[] = [
  {
    key: "dashboard",
    title: "Dashboard",
    href: "/dashboard",
    icon: LayoutGrid,
    keywords: ["dashboard", "overview", "home"],
  },
  { key: "home", title: "Home", href: "/", icon: Home, keywords: ["home", "landing"] },
  {
    key: "company",
    title: "Company",
    href: "/company",
    icon: Sparkles,
    keywords: ["company", "research", "intel", "intelligence"],
  },
  {
    key: "documents",
    title: "Documents",
    href: "/documents",
    icon: FileText,
    keywords: ["documents", "notes", "files"],
  },
  {
    key: "notion",
    title: "Notion",
    href: "/notion",
    icon: NotepadText,
    keywords: ["notion", "integration", "sync", "import"],
  },
  { key: "calendar", title: "Calendar", href: "/calendar", icon: Calendar, keywords: ["calendar"] },
  {
    key: "system-design",
    title: "System Design",
    href: "/system-design",
    icon: Shapes,
    keywords: ["system design", "diagram", "architecture"],
  },
  {
    key: "interview-prep",
    title: "Interview Prep",
    href: "/interview-prep",
    icon: BookOpen,
    keywords: ["interview", "prep", "questions", "practice"],
  },
  {
    key: "threads",
    title: "Threads",
    href: "/threads",
    icon: MessageSquareText,
    keywords: ["threads", "history", "messages", "conversation"],
  },
  { key: "rag", title: "RAG", href: "/rag", icon: MessageCircle, keywords: ["rag", "chat", "qa"] },
  {
    key: "tasks",
    title: "Tasks",
    href: "/tasks",
    icon: Command,
    keywords: ["tasks", "jobs", "queue"],
  },
  {
    key: "zettels",
    title: "Zettels",
    href: "/zettels",
    icon: Network,
    keywords: ["zettels", "zettelkasten", "cards", "links", "graph"],
  },
  {
    key: "whiteboards",
    title: "Whiteboards",
    href: "/whiteboards",
    icon: PenTool,
    keywords: ["whiteboards", "canvas", "revisions", "comments"],
  },
  {
    key: "writing",
    title: "Writing",
    href: "/writing",
    icon: Feather,
    keywords: ["writing", "compose", "rewrite", "presets", "stream"],
  },
  {
    key: "linear",
    title: "Linear",
    href: "/linear",
    icon: Sparkles,
    keywords: ["linear", "issues", "status"],
  },
  {
    key: "web",
    title: "Web",
    href: "/web",
    icon: Globe,
    keywords: ["web", "search", "wikipedia"],
  },
  {
    key: "mind-palace",
    title: "Mind Palace",
    href: "/mind-palace",
    icon: Brain,
    keywords: ["agent", "mind palace", "tools", "query"],
  },
  {
    key: "admin",
    title: "Admin",
    href: "/admin",
    icon: Shield,
    keywords: ["admin", "backlog", "concepts", "operations"],
  },
  {
    key: "tools",
    title: "Tools",
    href: "/tools",
    icon: Wrench,
    keywords: ["tools", "status", "slack", "store"],
  },
  {
    key: "design-system",
    title: "Design System",
    href: "/design-system",
    icon: Palette,
    keywords: ["design system", "ui", "components", "tokens"],
  },
];

export const appTopNavItems = appNavItems.filter((item) => item.topNav);
