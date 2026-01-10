"use client";

import Link from "next/link";

import { AppCommandPaletteTrigger } from "@/components/app-command-palette";
import { AppNavigationMenu } from "@/components/app-navigation-menu";
import { AppSidebar } from "@/components/app-sidebar";
import { AuthControls } from "@/components/auth/auth-controls";
import { TaskCenterTrigger } from "@/components/task-center-sheet";
import { ThemeToggle } from "@/components/theme-toggle";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

export function AppShell({
  children,
  defaultSidebarOpen,
}: {
  children: React.ReactNode;
  defaultSidebarOpen: boolean;
}) {
  return (
    <SidebarProvider defaultOpen={defaultSidebarOpen}>
      <AppSidebar />
      <SidebarInset>
        <header className="bg-background/90 supports-[backdrop-filter]:bg-background/60 sticky top-0 z-40 border-b backdrop-blur">
          <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3">
            <div className="flex items-center gap-3">
              <SidebarTrigger />
              <Link href="/" className="font-semibold tracking-tight">
                Alfred
              </Link>
              <span className="text-muted-foreground hidden text-xs sm:inline">
                Knowledge workbench
              </span>
            </div>
            <div className="flex items-center gap-2">
              <nav className="hidden items-center md:flex" aria-label="Primary navigation">
                <AppNavigationMenu />
              </nav>
              <AppCommandPaletteTrigger className="md:hidden" variant="icon" />
              <AppCommandPaletteTrigger className="hidden md:flex" />
              <TaskCenterTrigger />
              <ThemeToggle />
              <AuthControls />
            </div>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} className="focus:outline-none">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
