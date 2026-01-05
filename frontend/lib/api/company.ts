import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  CompanyResearchReportPayloadResponse,
  CompanyResearchReportSummary,
  CompanyResearchResponse,
} from "@/lib/api/types/company";

type CompanyResearchParams = {
  name: string;
  refresh?: boolean;
  background?: boolean;
};

function buildQuery(params: CompanyResearchParams): string {
  const query = new URLSearchParams();
  query.set("name", params.name);
  if (params.refresh) query.set("refresh", "true");
  if (params.background) query.set("background", "true");
  return query.toString();
}

export async function companyResearch(
  params: CompanyResearchParams,
): Promise<CompanyResearchResponse> {
  return apiFetch<CompanyResearchResponse>(`${apiRoutes.company.research}?${buildQuery(params)}`, {
    cache: "no-store",
  });
}

export async function listRecentCompanyResearchReports(
  limit = 20,
): Promise<CompanyResearchReportSummary[]> {
  const query = new URLSearchParams();
  query.set("limit", String(limit));
  return apiFetch<CompanyResearchReportSummary[]>(
    `${apiRoutes.company.researchReportsRecent}?${query.toString()}`,
    { cache: "no-store" },
  );
}

export async function getCompanyResearchReportById(
  reportId: string,
): Promise<CompanyResearchReportPayloadResponse> {
  return apiFetch<CompanyResearchReportPayloadResponse>(
    apiRoutes.company.researchReportById(reportId),
    { cache: "no-store" },
  );
}
