import { useQuery } from "@tanstack/react-query";

import {
  getResearchReportById,
  listRecentResearchReports,
} from "@/lib/api/research";

export function recentResearchReportsQueryKey(limit: number) {
  return ["research", "reports", "recent", limit] as const;
}

export function researchReportQueryKey(reportId: string) {
  return ["research", "reports", "by-id", reportId] as const;
}

export function useRecentResearchReports(limit = 20) {
  return useQuery({
    queryKey: recentResearchReportsQueryKey(limit),
    queryFn: () => listRecentResearchReports(limit),
    staleTime: 30_000,
  });
}

export function useResearchReport(reportId: string | null) {
  return useQuery({
    enabled: Boolean(reportId),
    queryKey: reportId
      ? researchReportQueryKey(reportId)
      : ["research", "reports", "disabled"],
    queryFn: () => getResearchReportById(reportId!),
    staleTime: 60_000,
  });
}
