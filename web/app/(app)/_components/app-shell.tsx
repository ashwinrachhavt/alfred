"use client";

import Link from "next/link";

import { SignedIn, SignedOut, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";

import { AppCommandPaletteTrigger } from "@/components/app-command-palette";
import { AppNavigationMenu } from "@/components/app-navigation-menu";
import { AppSidebar } from "@/components/app-sidebar";
import { AssistantTrigger } from "@/components/assistant-sheet";
import { TaskCenterTrigger } from "@/components/task-center-sheet";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { isClerkEnabled } from "@/lib/auth";

export function AppShell({
  children,
  defaultSidebarOpen,
}: {
  children: React.ReactNode;
  defaultSidebarOpen: boolean;
}) {
  const clerkEnabled = isClerkEnabled();

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
              <AssistantTrigger />
              <TaskCenterTrigger />
              <ThemeToggle />
              {clerkEnabled ? (
                <>
                  <SignedOut>
                    <SignInButton mode="modal">
                      <Button size="sm" variant="ghost">
                        Sign in
                      </Button>
                    </SignInButton>
                    <SignUpButton mode="modal">
                      <Button size="sm">Sign up</Button>
                    </SignUpButton>
                  </SignedOut>
                  <SignedIn>
                    <UserButton />
                  </SignedIn>
                </>
              ) : null}
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
