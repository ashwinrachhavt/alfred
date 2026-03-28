import { clerkMiddleware } from "@clerk/nextjs/server";
// import { createRouteMatcher } from "@clerk/nextjs/server";

/**
 * Public routes that do NOT require authentication.
 *
 * Everything else (the entire (app) route group — dashboard, company, notes,
 * library, system-design, etc.) requires sign-in.
 *
 * API routes are left public because they are proxied to the FastAPI backend
 * via Next.js rewrites — the backend handles its own auth if needed.
 */
// const isPublicRoute = createRouteMatcher([
//   "/",
//   "/sign-in(.*)",
//   "/sign-up(.*)",
//   "/api(.*)",
// ]);

export default clerkMiddleware(async (_auth, _request) => {
  // TODO: re-enable auth after Clerk keys are refreshed
  // if (!isPublicRoute(request)) {
  //   await auth.protect();
  // }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
