import {
  BookOpen,
  Calendar,
  Command,
  FileText,
  LayoutGrid,
  MessageCircle,
  MessageSquareText,
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
  { key: "home", title: "Home", href: "/", icon: LayoutGrid, keywords: ["home", "dashboard"] },
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
];

export const appTopNavItems = appNavItems.filter((item) => item.topNav);
