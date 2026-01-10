"use client";

import Link from "next/link";

import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
  UserButton,
} from "@clerk/nextjs";

import { Button } from "@/components/ui/button";

function isClerkEnabled(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim());
}

export function AuthControls() {
  if (!isClerkEnabled()) return null;

  return (
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
  );
}

export function AuthDisabledNotice() {
  if (isClerkEnabled()) return null;
  return (
    <div className="text-muted-foreground text-sm">
      Auth is disabled (missing <code className="bg-muted rounded px-1 py-0.5">NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code>
      ).{" "}
      <Link href="/" className="text-primary underline underline-offset-2">
        Back to app
      </Link>
      .
    </div>
  );
}

