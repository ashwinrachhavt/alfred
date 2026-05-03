"use client";

import Link from "next/link";

import { SignedIn, SignedOut, UserButton } from "@clerk/nextjs";

import { AppCommandPaletteTrigger } from "@/components/app-command-palette";
import { ThemePicker } from "@/components/theme-picker";
import { Button } from "@/components/ui/button";
import { isClerkEnabled } from "@/lib/auth";

export function TopBar() {
  const clerkEnabled = isClerkEnabled();

  return (
    <header className="bg-background/90 supports-[backdrop-filter]:bg-background/60 sticky top-0 z-40 border-b backdrop-blur">
      <div className="flex h-10 items-center justify-between px-4">
        {/* Left: breadcrumb area — can be filled by page-level components */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium tracking-widest text-[var(--alfred-text-tertiary)] uppercase">
            Polymath
          </span>
        </div>

        {/* Right: utilities */}
        <div className="flex items-center gap-1.5">
          <AppCommandPaletteTrigger />
          <ThemePicker />
          {clerkEnabled ? (
            <>
              <SignedOut>
                <Button asChild size="sm" variant="ghost" className="text-xs">
                  <Link href="/sign-in">Sign in</Link>
                </Button>
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
