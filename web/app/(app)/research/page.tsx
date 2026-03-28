import { ResearchClient } from "@/app/(app)/research/_components/research-client";
import { Page } from "@/components/layout/page";

type ResearchPageProps = {
  searchParams?: Promise<{
    reportId?: string | string[];
    topic?: string | string[];
    refresh?: string | string[];
  }>;
};

export default async function ResearchPage({ searchParams }: ResearchPageProps) {
  const resolvedSearchParams = await searchParams;
  const reportIdValue = resolvedSearchParams?.reportId;
  const reportId = Array.isArray(reportIdValue) ? reportIdValue[0] : reportIdValue;

  const topicValue = resolvedSearchParams?.topic;
  const topic = Array.isArray(topicValue) ? topicValue[0] : topicValue;

  const refreshValue = resolvedSearchParams?.refresh;
  const refreshRaw = Array.isArray(refreshValue) ? refreshValue[0] : refreshValue;
  const refresh = refreshRaw === "true" || refreshRaw === "1";

  return (
    <Page>
      <ResearchClient
        reportId={reportId}
        initialTopic={topic}
        initialRefresh={refresh}
      />
    </Page>
  );
}
