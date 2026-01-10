"use client";

import { ClerkProvider } from "@clerk/nextjs";

function isClerkEnabled(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY?.trim());
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  if (!isClerkEnabled()) return children;
  return <ClerkProvider>{children}</ClerkProvider>;
}

