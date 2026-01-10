import { ThreadsClient } from "@/app/(app)/threads/_components/threads-client";
import { Page } from "@/components/layout/page";

type ThreadsPageProps = {
  searchParams?: Promise<{
    title?: string | string[];
  }>;
};

function first(value: string | string[] | undefined): string | undefined {
  if (!value) return undefined;
  return Array.isArray(value) ? value[0] : value;
}

export default async function ThreadsPage({ searchParams }: ThreadsPageProps) {
  const params = await searchParams;
  const initialTitle = first(params?.title) ?? "";

  return (
    <Page size="comfortable">
      <ThreadsClient initialTitle={initialTitle} />
    </Page>
  );
}
