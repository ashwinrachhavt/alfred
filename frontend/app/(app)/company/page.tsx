import { CompanyResearchClient } from "@/app/(app)/company/_components/company-research-client";
import { Page } from "@/components/layout/page";

type CompanyPageProps = {
  searchParams?: {
    reportId?: string | string[];
  };
};

export default function CompanyPage({ searchParams }: CompanyPageProps) {
  const reportId = Array.isArray(searchParams?.reportId)
    ? searchParams?.reportId[0]
    : searchParams?.reportId;

  return (
    <Page>
      <CompanyResearchClient reportId={reportId} />
    </Page>
  );
}
