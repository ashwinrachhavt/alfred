"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  BookOpen,
  Calendar,
  Command,
  FileText,
  LayoutGrid,
  MessageCircle,
  Shapes,
  Sparkles,
} from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

type NavItem = {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
};

const primaryItems: NavItem[] = [
  { title: "Home", href: "/", icon: LayoutGrid },
  { title: "Company", href: "/company", icon: Sparkles },
  { title: "Documents", href: "/documents", icon: FileText },
  { title: "Calendar", href: "/calendar", icon: Calendar },
  { title: "System Design", href: "/system-design", icon: Shapes },
  { title: "Interview Prep", href: "/interview-prep", icon: BookOpen },
  { title: "RAG", href: "/rag", icon: MessageCircle },
  { title: "Tasks", href: "/tasks", icon: Command },
];

export function AppSidebar() {
  const pathname = usePathname();

  return (
    <Sidebar collapsible="icon">
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Alfred</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {primaryItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton asChild isActive={pathname === item.href}>
                    <Link href={item.href}>
                      <item.icon className="h-4 w-4 shrink-0" />
                      <span className="truncate group-data-[state=collapsed]:hidden">
                        {item.title}
                      </span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="space-y-2" />
    </Sidebar>
  );
}
