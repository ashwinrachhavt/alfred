import { ThreadDetailClient } from "@/app/(app)/threads/_components/thread-detail-client";
import { Page } from "@/components/layout/page";

type ThreadDetailPageProps = {
  params: { threadId: string } | Promise<{ threadId: string }>;
};

export default async function ThreadDetailPage({ params }: ThreadDetailPageProps) {
  const resolvedParams = await Promise.resolve(params);
  const threadId = resolvedParams.threadId;

  return (
    <Page size="comfortable">
      <ThreadDetailClient threadId={threadId} />
    </Page>
  );
}
