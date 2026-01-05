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
    researchReportsRecent: "/api/company/research-reports/recent",
    researchReportById: (reportId: string) => `/api/company/research-reports/${reportId}`,
  },
  tasks: {
    status: (taskId: string) => `/api/tasks/${taskId}`,
  },
} as const;
