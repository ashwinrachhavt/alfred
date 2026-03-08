import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

const isPublicRoute = createRouteMatcher(["/", "/sign-in(.*)", "/sign-up(.*)"]);

/**
 * Backend API routes are served by FastAPI and reached via Next.js rewrites.
 *
 * We intentionally do not guard these with Clerk middleware in Next.js to avoid
 * local/dev auth misconfiguration breaking core app functionality (the backend
 * should enforce auth if/when required).
 *
 * Note: Keep this list aligned with `frontend/next.config.js` rewrites.
 */
const isBackendApiRoute = createRouteMatcher([
  "/api/company(.*)",
  "/api/documents(.*)",
  "/api/v1/notes(.*)",
  "/api/v1/workspaces(.*)",
  "/api/rag(.*)",
  "/api/tasks(.*)",
]);

export default clerkEnabled
  ? clerkMiddleware(async (auth, req) => {
      if (isBackendApiRoute(req)) return;

      if (!isPublicRoute(req)) {
        await auth.protect();
      }
    })
  : function middleware() {};

export const config = {
  matcher: [
    // Skip Next.js internals and all static files, unless found in search params
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};
