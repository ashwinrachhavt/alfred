"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Sparkles } from "lucide-react";

import {
  appNavItems,
  navGroupLabels,
  navGroupOrder,
  type NavGroup,
} from "@/lib/navigation";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";

const itemsByGroup = navGroupOrder.reduce(
  (acc, group) => {
    acc[group] = appNavItems.filter((item) => item.group === group);
    return acc;
  },
  {} as Record<NavGroup, typeof appNavItems>,
);

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname();

  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild size="lg" className="data-[slot=sidebar-menu-button]:!p-1.5">
              <Link href="/dashboard" className="gap-2">
                <Sparkles className="size-5" aria-hidden="true" />
                <span className="text-base font-semibold tracking-tight">Alfred</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {navGroupOrder.map((group, groupIndex) => {
          const items = itemsByGroup[group];
          if (!items.length) return null;

          return (
            <div key={group}>
              {groupIndex > 0 ? <SidebarSeparator /> : null}
              <SidebarGroup>
                <SidebarGroupLabel>{navGroupLabels[group]}</SidebarGroupLabel>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {items.map((item) => {
                      const isActive =
                        pathname === item.href || pathname.startsWith(`${item.href}/`);

                      return (
                        <SidebarMenuItem key={item.key}>
                          <SidebarMenuButton
                            asChild
                            tooltip={item.title}
                            isActive={isActive}
                          >
                            <Link href={item.href}>
                              <item.icon className="size-4" aria-hidden="true" />
                              <span>{item.title}</span>
                            </Link>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      );
                    })}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            </div>
          );
        })}
      </SidebarContent>

      <SidebarFooter>
        <div className="text-muted-foreground px-2 py-1 text-xs">
          <span className="hidden md:inline">Search: ⌘K / Ctrl K</span>
          <span className="md:hidden">⌘K</span>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
