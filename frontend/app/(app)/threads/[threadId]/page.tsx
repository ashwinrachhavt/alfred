import { ThreadDetailClient } from "@/app/(app)/threads/_components/thread-detail-client";
import { Page } from "@/components/layout/page";

type ThreadDetailPageProps = {
  params: Promise<{ threadId: string }>;
};

export default async function ThreadDetailPage({ params }: ThreadDetailPageProps) {
  const { threadId } = await params;

  return (
    <Page size="comfortable">
      <ThreadDetailClient threadId={threadId} />
    </Page>
  );
}
