import { ThreadDetailClient } from "@/app/(app)/threads/_components/thread-detail-client";
import { Page } from "@/components/layout/page";

type ThreadDetailPageProps = {
  params: { threadId: string };
};

export default function ThreadDetailPage({ params }: ThreadDetailPageProps) {
  const { threadId } = params;

  return (
    <Page size="comfortable">
      <ThreadDetailClient threadId={threadId} />
    </Page>
  );
}
