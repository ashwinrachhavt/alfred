"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Sparkles } from "lucide-react";

import { appNavItems } from "@/lib/navigation";
import { useFollowUps } from "@/features/follow-ups/follow-up-provider";
import { useTaskTracker } from "@/features/tasks/task-tracker-provider";

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

const developerNavKeys = new Set(["design-system"]);

export function AppSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const pathname = usePathname();
  const { dueNowCount } = useFollowUps();
  const { activeCount } = useTaskTracker();

  const primaryNavItems = appNavItems.filter(
    (item) => item.key !== "home" && !developerNavKeys.has(item.key),
  );
  const developerNavItems = appNavItems.filter((item) => developerNavKeys.has(item.key));

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
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {primaryNavItems.map((item) => (
                <SidebarMenuItem key={item.key}>
                  <SidebarMenuButton
                    asChild
                    tooltip={item.title}
                    isActive={pathname === item.href || pathname.startsWith(`${item.href}/`)}
                  >
                    <Link href={item.href}>
                      <item.icon className="size-4" aria-hidden="true" />
                      <span>{item.title}</span>
                      {item.key === "tasks" ? (
                        <div
                          suppressHydrationWarning
                          className={`bg-destructive text-destructive-foreground ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[10px] font-medium ${activeCount ? "" : "hidden"}`}
                        >
                          {activeCount ?? ""}
                        </div>
                      ) : null}
                      {item.key === "follow-ups" ? (
                        <div
                          suppressHydrationWarning
                          className={`bg-destructive text-destructive-foreground ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[10px] font-medium ${dueNowCount ? "" : "hidden"}`}
                        >
                          {dueNowCount ?? ""}
                        </div>
                      ) : null}
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {developerNavItems.length ? (
          <>
            <SidebarSeparator />
            <SidebarGroup>
              <SidebarGroupLabel>Developer</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {developerNavItems.map((item) => (
                    <SidebarMenuItem key={item.key}>
                      <SidebarMenuButton
                        asChild
                        tooltip={item.title}
                        isActive={pathname === item.href || pathname.startsWith(`${item.href}/`)}
                      >
                        <Link href={item.href}>
                          <item.icon className="size-4" aria-hidden="true" />
                          <span>{item.title}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </>
        ) : null}
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
