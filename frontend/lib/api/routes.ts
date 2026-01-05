/**
 * Canonical frontend API routes.
 *
 * The frontend always calls `/api/*` and relies on Next.js rewrites to reach the
 * correct backend prefix (some FastAPI routers are mounted outside `/api/*`).
 */
export const apiRoutes = {
  company: {
    research: "/api/company/research",
    insights: "/api/company/insights",
    outreach: "/api/company/outreach",
  },
  tasks: {
    status: (taskId: string) => `/api/tasks/${taskId}`,
  },
} as const
