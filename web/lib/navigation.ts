import { Brain, Inbox, LayoutDashboard, Network, type LucideIcon } from "lucide-react";

export type PillarKey = "inbox" | "canvas" | "ai" | "dashboard";

export type PillarItem = {
  key: PillarKey;
  title: string;
  href: string;
  icon: LucideIcon;
  shortcut: string;
};

export const pillars: PillarItem[] = [
  { key: "inbox", title: "Inbox", href: "/inbox", icon: Inbox, shortcut: "1" },
  { key: "canvas", title: "Canvas", href: "/canvas", icon: Network, shortcut: "2" },
  { key: "ai", title: "AI", href: "#ai", icon: Brain, shortcut: "3" },
  { key: "dashboard", title: "Dashboard", href: "/dashboard", icon: LayoutDashboard, shortcut: "4" },
];
