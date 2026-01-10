import { useQuery } from "@tanstack/react-query";

import {
  getCompanyResearchReportById,
  listCompanyContactsFromDb,
  listRecentCompanyResearchReports,
} from "@/lib/api/company";

export function recentCompanyResearchReportsQueryKey(limit: number) {
  return ["company", "research-reports", "recent", limit] as const;
}

export function companyResearchReportQueryKey(reportId: string) {
  return ["company", "research-reports", "by-id", reportId] as const;
}

export function useRecentCompanyResearchReports(limit = 20) {
  return useQuery({
    queryKey: recentCompanyResearchReportsQueryKey(limit),
    queryFn: () => listRecentCompanyResearchReports(limit),
  });
}

export function useCompanyResearchReport(reportId: string | null) {
  return useQuery({
    enabled: Boolean(reportId),
    queryKey: reportId
      ? companyResearchReportQueryKey(reportId)
      : ["company", "research-reports", "disabled"],
    queryFn: () => getCompanyResearchReportById(reportId!),
  });
}

export function companyContactsDbQueryKey(params: {
  name: string;
  role?: string;
  limit: number;
}) {
  return ["company", "contacts", "db", params.name, params.role ?? null, params.limit] as const;
}

export function useCompanyContactsFromDb(params: { name: string; role?: string; limit?: number }) {
  const name = params.name.trim();
  const role = params.role?.trim() || undefined;
  const limit = params.limit ?? 20;

  return useQuery({
    enabled: Boolean(name),
    queryKey: companyContactsDbQueryKey({ name, role, limit }),
    queryFn: () => listCompanyContactsFromDb({ name, role, limit }),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}
