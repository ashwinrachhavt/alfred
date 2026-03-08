import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type {
  CompanyContactsDbResponse,
  CompanyContactsDbRecentResponse,
  CompanyContactsDiscoverResponse,
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

type CompanyContactsParams = {
  name: string;
  role?: string;
  limit?: number;
  refresh?: boolean;
};

function buildContactsQuery(params: CompanyContactsParams): string {
  const query = new URLSearchParams();
  query.set("name", params.name);
  if (params.role) query.set("role", params.role);
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (params.refresh) query.set("refresh", "true");
  return query.toString();
}

export async function discoverCompanyContacts(
  params: CompanyContactsParams,
): Promise<CompanyContactsDiscoverResponse> {
  return apiFetch<CompanyContactsDiscoverResponse>(
    `${apiRoutes.company.contacts}?${buildContactsQuery(params)}`,
    { cache: "no-store" },
  );
}

export async function listCompanyContactsFromDb(
  params: Omit<CompanyContactsParams, "refresh">,
): Promise<CompanyContactsDbResponse> {
  return apiFetch<CompanyContactsDbResponse>(
    `${apiRoutes.company.contactsDb}?${buildContactsQuery(params)}`,
    { cache: "no-store" },
  );
}

type CompanyContactsRecentParams = {
  q?: string;
  company?: string;
  role?: string;
  limit?: number;
  offset?: number;
};

function buildContactsRecentQuery(params: CompanyContactsRecentParams): string {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.company) query.set("company", params.company);
  if (params.role) query.set("role", params.role);
  if (typeof params.limit === "number") query.set("limit", String(params.limit));
  if (typeof params.offset === "number") query.set("offset", String(params.offset));
  return query.toString();
}

export async function listRecentCompanyContactsFromDb(
  params: CompanyContactsRecentParams,
): Promise<CompanyContactsDbRecentResponse> {
  const query = buildContactsRecentQuery(params);
  const suffix = query ? `?${query}` : "";
  return apiFetch<CompanyContactsDbRecentResponse>(`${apiRoutes.company.contactsDbRecent}${suffix}`, {
    cache: "no-store",
  });
}
