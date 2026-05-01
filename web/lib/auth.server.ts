import { auth } from "@clerk/nextjs/server";

import { isClerkEnabled } from "@/lib/auth";

/**
 * Safe auth wrapper for server-only contexts (API routes, server components).
 * Returns `{ userId }` from Clerk when enabled, or `{ userId: "local" }` when
 * Clerk is not configured so the app works without authentication.
 */
export async function getAuth(): Promise<{ userId: string | null }> {
  if (!isClerkEnabled()) {
    return { userId: "local" };
  }
  return auth();
}
