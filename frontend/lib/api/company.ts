import { apiFetch, apiPostJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  CompanyContactsResponse,
  CompanyInsightsResponse,
  CompanyResearchReportPayloadResponse,
  CompanyResearchReportSummary,
  CompanyResearchResponse,
  CompanyOutreachResponse,
  ContactProvider,
  OutreachRequest,
  OutreachSendRequest,
  OutreachSendResponse,
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

type CompanyInsightsParams = {
  name: string;
  role?: string | null;
  refresh?: boolean;
  background?: boolean;
};

function buildCompanyInsightsQuery(params: CompanyInsightsParams): string {
  const query = new URLSearchParams();
  query.set("name", params.name);
  if (params.role) query.set("role", params.role);
  if (params.refresh) query.set("refresh", "true");
  if (params.background) query.set("background", "true");
  return query.toString();
}

export async function companyInsights(params: CompanyInsightsParams): Promise<CompanyInsightsResponse> {
  return apiFetch<CompanyInsightsResponse>(
    `${apiRoutes.company.insights}?${buildCompanyInsightsQuery(params)}`,
    { cache: "no-store" },
  );
}

type CompanyOutreachGetParams = {
  name: string;
  role?: string;
};

function buildCompanyOutreachGetQuery(params: CompanyOutreachGetParams): string {
  const query = new URLSearchParams();
  query.set("name", params.name);
  if (params.role) query.set("role", params.role);
  return query.toString();
}

export async function companyOutreachGet(
  params: CompanyOutreachGetParams,
): Promise<CompanyOutreachResponse> {
  return apiFetch<CompanyOutreachResponse>(
    `${apiRoutes.company.outreach}?${buildCompanyOutreachGetQuery(params)}`,
    { cache: "no-store" },
  );
}

export async function companyOutreachPost(body: OutreachRequest): Promise<CompanyOutreachResponse> {
  return apiPostJson<CompanyOutreachResponse, OutreachRequest>(apiRoutes.company.outreach, body, {
    cache: "no-store",
  });
}

type CompanyContactsParams = {
  name: string;
  role?: string | null;
  limit?: number;
  refresh?: boolean;
  providers?: ContactProvider[] | null;
};

export async function companyContacts(params: CompanyContactsParams): Promise<CompanyContactsResponse> {
  const query = new URLSearchParams();
  query.set("name", params.name);
  if (params.role) query.set("role", params.role);
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (params.refresh) query.set("refresh", "true");
  if (params.providers?.length) {
    params.providers.forEach((provider) => query.append("providers", provider));
  }
  return apiFetch<CompanyContactsResponse>(`${apiRoutes.company.contacts}?${query.toString()}`, {
    cache: "no-store",
  });
}

export async function companyOutreachSend(body: OutreachSendRequest): Promise<OutreachSendResponse> {
  return apiPostJson<OutreachSendResponse, OutreachSendRequest>(apiRoutes.company.outreachSend, body, {
    cache: "no-store",
  });
}
