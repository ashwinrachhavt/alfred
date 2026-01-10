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
  documents: {
    explorer: "/api/documents/explorer",
    semanticMap: "/api/documents/semantic-map",
    documentDetails: (id: string) => `/api/documents/${id}/details`,
    documentText: (id: string) => `/api/documents/${id}/text`,
    documentImage: (id: string) => `/api/documents/${id}/image`,
    documentImageAsync: (id: string) => `/api/documents/${id}/image/async`,
  },
  threads: {
    list: "/api/threads",
    create: "/api/threads",
    messages: (threadId: string) => `/api/threads/${threadId}/messages`,
  },
  tasks: {
    status: (taskId: string) => `/api/tasks/${taskId}`,
  },
  intelligence: {
    autocomplete: "/api/intelligence/autocomplete",
    edit: "/api/intelligence/edit",
  },
} as const;
