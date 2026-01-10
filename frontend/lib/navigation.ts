import {
  Bell,
  BookOpen,
  Calendar,
  Command,
  FileText,
  Home,
  LayoutGrid,
  MessageCircle,
  MessageSquareText,
  NotepadText,
  Palette,
  Shapes,
  Sparkles,
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
  {
    key: "calendar",
    title: "Calendar",
    href: "/calendar",
    icon: Calendar,
    keywords: ["calendar", "email", "gmail", "scan", "inbox"],
  },
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
    key: "follow-ups",
    title: "Follow-ups",
    href: "/follow-ups",
    icon: Bell,
    keywords: ["follow ups", "follow-ups", "reminders", "pending", "nudge"],
  },
  {
    key: "tasks",
    title: "Tasks",
    href: "/tasks",
    icon: Command,
    keywords: ["tasks", "jobs", "queue"],
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
