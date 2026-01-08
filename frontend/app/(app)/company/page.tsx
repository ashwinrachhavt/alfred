import { CompanyResearchClient } from "@/app/(app)/company/_components/company-research-client";
import { Page } from "@/components/layout/page";

type CompanyPageProps = {
  searchParams?: Promise<{
    reportId?: string | string[];
  }>;
};

export default async function CompanyPage({ searchParams }: CompanyPageProps) {
  const resolvedSearchParams = await searchParams;
  const reportIdValue = resolvedSearchParams?.reportId;
  const reportId = Array.isArray(reportIdValue) ? reportIdValue[0] : reportIdValue;

  return (
    <Page>
      <CompanyResearchClient reportId={reportId} />
    </Page>
  );
}
