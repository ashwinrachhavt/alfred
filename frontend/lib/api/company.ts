import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import type { CompanyResearchResponse } from "@/lib/api/types/company";

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
