"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Clock } from "lucide-react";

import { appNavItems } from "@/lib/navigation";

import { CompanyResearchHistorySheet } from "@/components/company-research-history-sheet";
import { InterviewPrepSessionHistorySheet } from "@/components/interview-prep-session-history-sheet";
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

export function AppSidebar() {
  const pathname = usePathname();
  const isCompanyRoute = pathname === "/company" || pathname.startsWith("/company/");
  const isInterviewPrepRoute =
    pathname === "/interview-prep" || pathname.startsWith("/interview-prep/");

  return (
    <Sidebar collapsible="icon">
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Alfred</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {appNavItems.map((item) => (
                <SidebarMenuItem key={item.key}>
                  <SidebarMenuButton asChild isActive={pathname === item.href}>
                    <Link href={item.href}>
                      <item.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
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

        {isCompanyRoute ? (
          <SidebarGroup>
            <SidebarGroupLabel>Company</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <CompanyResearchHistorySheet
                    trigger={
                      <SidebarMenuButton type="button">
                        <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
                        <span className="truncate group-data-[state=collapsed]:hidden">
                          Recent research
                        </span>
                      </SidebarMenuButton>
                    }
                  />
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ) : null}

        {isInterviewPrepRoute ? (
          <SidebarGroup>
            <SidebarGroupLabel>Interview prep</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <InterviewPrepSessionHistorySheet
                    trigger={
                      <SidebarMenuButton type="button">
                        <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
                        <span className="truncate group-data-[state=collapsed]:hidden">
                          Recent sessions
                        </span>
                      </SidebarMenuButton>
                    }
                  />
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ) : null}
      </SidebarContent>

      <SidebarFooter className="space-y-2" />
    </Sidebar>
  );
}
