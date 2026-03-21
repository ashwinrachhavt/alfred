"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";

import { AppCommandPaletteTrigger } from "@/components/app-command-palette";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { isClerkEnabled } from "@/lib/auth";
import { pillars } from "@/lib/navigation";
import { useShellStore } from "@/lib/stores/shell-store";

export function TopBar() {
  const pathname = usePathname();
  const toggleAiPanel = useShellStore((s) => s.toggleAiPanel);
  const aiPanelOpen = useShellStore((s) => s.aiPanelOpen);
  const clerkEnabled = isClerkEnabled();

  return (
    <header className="bg-background/90 supports-[backdrop-filter]:bg-background/60 sticky top-0 z-40 border-b backdrop-blur">
      <div className="flex h-12 items-center justify-between px-4">
        <div className="flex items-center gap-1">
          <Link href="/inbox" className="mr-4 flex items-center gap-2 font-semibold tracking-tight">
            <span className="text-primary text-lg">◆</span>
            <span className="hidden sm:inline">Alfred</span>
          </Link>
          <nav className="flex items-center gap-0.5" aria-label="Primary navigation">
            {pillars.map((p) => {
              if (p.key === "ai") {
                return (
                  <Tooltip key={p.key}>
                    <TooltipTrigger asChild>
                      <Button
                        variant={aiPanelOpen ? "secondary" : "ghost"}
                        size="sm"
                        onClick={toggleAiPanel}
                        className="gap-1.5"
                      >
                        <p.icon className="size-4" />
                        <span className="hidden md:inline">{p.title}</span>
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Toggle AI Panel (⌘J)</TooltipContent>
                  </Tooltip>
                );
              }

              const isActive = pathname === p.href || pathname.startsWith(`${p.href}/`);
              return (
                <Tooltip key={p.key}>
                  <TooltipTrigger asChild>
                    <Button variant={isActive ? "secondary" : "ghost"} size="sm" asChild className="gap-1.5">
                      <Link href={p.href}>
                        <p.icon className="size-4" />
                        <span className="hidden md:inline">{p.title}</span>
                      </Link>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{p.title} (⌘{p.shortcut})</TooltipContent>
                </Tooltip>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-1.5">
          <AppCommandPaletteTrigger />
          <ThemeToggle />
          {clerkEnabled ? (
            <>
              <SignedOut>
                <SignInButton mode="modal">
                  <Button size="sm" variant="ghost">Sign in</Button>
                </SignInButton>
              </SignedOut>
              <SignedIn>
                <UserButton />
              </SignedIn>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}
