import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  ResearchReportPayloadResponse,
  ResearchReportSummary,
  ResearchResponse,
} from "@/lib/api/types/research";

type DeepResearchParams = {
  topic: string;
  refresh?: boolean;
  background?: boolean;
};

function buildQuery(params: DeepResearchParams): string {
  const query = new URLSearchParams();
  query.set("topic", params.topic);
  if (params.refresh) query.set("refresh", "true");
  if (params.background) query.set("background", "true");
  return query.toString();
}

export async function deepResearch(
  params: DeepResearchParams,
): Promise<ResearchResponse> {
  return apiFetch<ResearchResponse>(`${apiRoutes.research.deepResearch}?${buildQuery(params)}`, {
    cache: "no-store",
  });
}

export async function listRecentResearchReports(
  limit = 20,
): Promise<ResearchReportSummary[]> {
  const query = new URLSearchParams();
  query.set("limit", String(limit));
  return apiFetch<ResearchReportSummary[]>(
    `${apiRoutes.research.reportsRecent}?${query.toString()}`,
    { cache: "no-store" },
  );
}

export async function getResearchReportById(
  reportId: string,
): Promise<ResearchReportPayloadResponse> {
  return apiFetch<ResearchReportPayloadResponse>(
    apiRoutes.research.reportById(reportId),
    { cache: "no-store" },
  );
}
