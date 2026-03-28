"use client";

import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/nextjs";

import { AppCommandPaletteTrigger } from "@/components/app-command-palette";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { isClerkEnabled } from "@/lib/auth";

export function TopBar() {
  const clerkEnabled = isClerkEnabled();

  return (
    <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-10 items-center justify-between px-4">
        {/* Left: breadcrumb area — can be filled by page-level components */}
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
            Alfred
          </span>
        </div>

        {/* Right: utilities */}
        <div className="flex items-center gap-1.5">
          <AppCommandPaletteTrigger />
          <ThemeToggle />
          {clerkEnabled ? (
            <>
              <SignedOut>
                <SignInButton mode="modal">
                  <Button size="sm" variant="ghost" className="font-mono text-xs">
                    Sign in
                  </Button>
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
