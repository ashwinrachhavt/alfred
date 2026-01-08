import { Page } from "@/components/layout/page";

import { DocumentReaderClient } from "./_components/document-reader-client";

export default function DocumentReaderPage({ params }: { params: { id: string } }) {
  return (
    <Page size="comfortable">
      <DocumentReaderClient docId={params.id} />
    </Page>
  );
}

