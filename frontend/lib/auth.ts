/**
 * Returns `true` when Clerk authentication is configured for the frontend.
 *
 * This is intentionally based on the `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` env var so
 * that both server and client components can gate Clerk-only UI safely.
 */
export function isClerkEnabled(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
}
