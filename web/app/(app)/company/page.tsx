import { CompanyResearchClient } from "@/app/(app)/company/_components/company-research-client";
import { Page } from "@/components/layout/page";

type CompanyPageProps = {
  searchParams?: Promise<{
    reportId?: string | string[];
    company?: string | string[];
    refresh?: string | string[];
  }>;
};

export default async function CompanyPage({ searchParams }: CompanyPageProps) {
  const resolvedSearchParams = await searchParams;
  const reportIdValue = resolvedSearchParams?.reportId;
  const reportId = Array.isArray(reportIdValue) ? reportIdValue[0] : reportIdValue;

  const companyValue = resolvedSearchParams?.company;
  const company = Array.isArray(companyValue) ? companyValue[0] : companyValue;

  const refreshValue = resolvedSearchParams?.refresh;
  const refreshRaw = Array.isArray(refreshValue) ? refreshValue[0] : refreshValue;
  const refresh = refreshRaw === "true" || refreshRaw === "1";

  return (
    <Page>
      <CompanyResearchClient
        reportId={reportId}
        initialCompany={company}
        initialRefresh={refresh}
      />
    </Page>
  );
}
