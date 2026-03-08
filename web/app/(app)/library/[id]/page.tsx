import { Page } from "@/components/layout/page";
import { DocumentReaderClient } from "@/app/(app)/documents/[id]/_components/document-reader-client";

type LibraryDocumentPageProps = {
  params: { id: string } | Promise<{ id: string }>;
};

export default async function LibraryDocumentPage({ params }: LibraryDocumentPageProps) {
  const resolvedParams = await Promise.resolve(params);

  return (
    <Page size="comfortable">
      <DocumentReaderClient docId={resolvedParams.id} />
    </Page>
  );
}
